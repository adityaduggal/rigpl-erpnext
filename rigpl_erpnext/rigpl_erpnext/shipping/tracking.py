"""
Tracking jobs and the one writer of tracking data (#168, #152, #169).

- `apply_tracking_results` writes the results of a batch. Submitted trackings get one
  UPDATE for the batch (`bulk_update_rows`), and the scans of the changed ones are replaced
  with 1 DELETE and 1 INSERT for each chunk. A draft is submitted with
  `submit()` (never `docstatus = 1`), because it must run its hooks.
- `poll_open_shipments` (hourly) selects the trackings to poll with one query, with all the
  filters in SQL, and calls each provider in batches.
- `push_to_aggregator` (hourly) sends new AWBs of Shipway carriers to Shipway.
- `unpublish_ctracks` (daily) is one UPDATE.
- `refresh_and_close_stale` (by hand only, #169) polls the old open trackings one last time,
  closes the rest as "Closed - No Update" and adds a Comment with the old status to each.
"""
from collections import defaultdict
from datetime import timedelta
from typing import Dict, Iterable, List, Optional, Tuple

import frappe
from frappe.query_builder.functions import Coalesce, Count, Max
from frappe.utils import add_days, get_datetime, getdate, now_datetime, nowdate
from pypika import Order

from ...utils.batch_write_utils import bulk_insert_rows, bulk_set_fields, bulk_update_rows
from ...utils.item_attribute_utils import chunks
from . import status as st
from .base import ProviderError, TrackingResult
from .registry import Carrier, get_carriers
from .settings import ShippingSettings, get_shipping_settings
from .status_map import record_unknown

DOCTYPE = "Carrier Tracking"
SCANS = "Courier Tracking Scans"
NO_AWB = ("", "NA")
# The old jobs did not poll a tracking on its first day (API) or first 2 days (Shipway).
API_MIN_AGE_DAYS, SHIPWAY_MIN_AGE_DAYS = 2, 3
RESULT_FIELDS = ("status", "status_code", "pickup_date", "expected_delivery_date", "delivery_date_time",
                 "recipient", "ship_to_city", "last_update", "tracking_source")


# ----------------------------------------------------------------------------------------- jobs

def daily_shipping_jobs():
    """Only unpublishes. Closing stale trackings is done by hand (#169)."""
    unpublish_ctracks()
    frappe.db.commit()


def poll_open_shipments(settings: Optional[ShippingSettings] = None) -> Dict[str, int]:
    settings = settings or get_shipping_settings()
    return track_rows(select_open_shipments(settings), source="Poll", commit=True)


# ------------------------------------------------------------------------------------- selection

def base_query(count: bool = False):
    """Carrier Trackings with an AWB, joined to their Transporter and enabled account.
    With `count`, it selects only COUNT(name)."""
    ct, tpt, acc = frappe.qb.DocType(DOCTYPE), frappe.qb.DocType("Transporters"), frappe.qb.DocType("Shipping Provider Account")
    query = (
        frappe.qb.from_(ct)
        .join(tpt).on(tpt.name == ct.carrier_name)
        .join(acc).on(acc.name == tpt.shipping_provider_account)
        .where(ct.docstatus < 2)
        .where(ct.awb_number.notnull())
        .where(ct.awb_number.notin(NO_AWB))
        .where(tpt.api_mode != "None")
        .where(acc.enabled == 1)
    )
    if count:
        query = query.select(Count(ct.name).as_("count"))
    else:
        query = query.select(ct.name, ct.awb_number, ct.carrier_name, ct.docstatus, *[ct[f] for f in RESULT_FIELDS],
                             acc.provider)
    return query, ct, tpt, acc


def select_open_shipments(settings: ShippingSettings, now=None) -> List[dict]:
    """The trackings to poll now, in one query. The same rules as the old `get_all_ship_data`
    (#152), with the age and last-update filters in SQL:
    - not in a final status, and not taken out of tracking by hand;
    - Shipway: pushed to Shipway, and 3 to `shipway_max_track_days` - 1 days old;
    - API carriers: 2 to `max_track_days` - 1 days old;
    - not updated in the last `ctrack_poll_hours` (`ctrack_webhook_poll_hours` with webhooks).
    The old jobs used `modified` as the last update. `last_update` is used when it is set."""
    now = get_datetime(now or now_datetime())
    today = getdate(now)
    query, ct, _tpt, acc = base_query()
    is_shipway = acc.provider == "Shipway"
    last = Coalesce(ct.last_update, ct.modified)
    poll_before = now - timedelta(hours=settings.ctrack_poll_hours)
    webhook_poll_before = now - timedelta(hours=settings.ctrack_webhook_poll_hours)

    def age_between(min_days, max_days):
        # whole days as the old jobs counted them: (today - creation date)
        return (ct.creation < add_days(today, -(min_days - 1))) & (ct.creation >= add_days(today, -(max_days - 1)))

    query = (
        query.where(ct.status.isnull() | ct.status.notin(st.FINAL_STATUSES))
        .where(ct.manual_exception_removed == 0)
        .where(
            (is_shipway & (ct.posted_to_shipway == 1) & age_between(SHIPWAY_MIN_AGE_DAYS, settings.shipway_max_track_days))
            | (~is_shipway & age_between(API_MIN_AGE_DAYS, settings.max_track_days))
        )
        .where(
            ((acc.webhook_enabled == 1) & (last < webhook_poll_before))
            | ((acc.webhook_enabled == 0) & (last < poll_before))
        )
        .orderby(ct.creation)
    )
    return query.run(as_dict=True)


# ------------------------------------------------------------------------------------- tracking

def track_rows(rows: List[dict], source: str, commit: bool = False) -> Dict[str, int]:
    """Calls each provider for `rows` in batches and writes the results. A batch that fails
    is logged and skipped, so one bad carrier does not stop the others."""
    counts = defaultdict(int)
    carriers = get_carriers(r["carrier_name"] for r in rows)
    by_carrier = defaultdict(list)
    for row in rows:
        by_carrier[row["carrier_name"]].append(row)
    for transporter, carrier_rows in by_carrier.items():
        carrier = carriers.get(transporter)
        if not carrier or not carrier.provider.supports("track"):
            counts["skipped"] += len(carrier_rows)
            continue
        for batch in chunks_of(carrier_rows, carrier.provider.track_batch_size):
            try:
                results = carrier.provider.track_many({r["awb_number"]: r["name"] for r in batch})
            except ProviderError as e:
                frappe.log_error(str(e)[:1000], f"Shipping: {carrier.provider.name} tracking failed")
                counts["failed"] += len(batch)
                continue
            for key, value in apply_tracking_results(batch, results, source).items():
                counts[key] += value
            if commit:
                frappe.db.commit()
    record_unknown({id(c.provider.resolve): c.provider.resolve for c in carriers.values()}.values())
    if commit:
        frappe.db.commit()
    return dict(counts)


def chunks_of(rows: List[dict], size: int) -> Iterable[List[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def result_values(row: dict, result: TrackingResult, source: str, now) -> dict:
    """The new field values of one tracking. Pure. A result that is not found only moves
    `last_update`, so the tracking keeps its data and is polled later."""
    values = {"last_update": now, "tracking_source": source}
    if not result.found:
        return values
    values.update(status=result.status, status_code=(result.status_code or "")[:140])
    for field, value in (("pickup_date", result.pickup_date and getdate(result.pickup_date)),
                         ("expected_delivery_date", result.expected_delivery_date),
                         ("delivery_date_time", result.delivery_date_time),
                         ("recipient", result.recipient), ("ship_to_city", result.destination)):
        if value:
            values[field] = value
    if result.status != st.DELIVERED:
        values["delivery_date_time"] = None
    return values


def apply_tracking_results(rows: List[dict], results: Dict[str, TrackingResult], source: str) -> Dict[str, int]:
    """Writes a batch of results. `rows` are the selected trackings (name, awb_number,
    docstatus and the RESULT_FIELDS). 1 UPDATE for the batch, and 3 queries for the scans."""
    now = now_datetime()
    new, drafts, scans = {}, [], {}
    counts = defaultdict(int)
    for row in rows:
        result = results.get(row["awb_number"])
        if not result:
            continue
        values = result_values(row, result, source, now)
        if result.found:
            counts[result.status] += 1
            scans[row["name"]] = result.scans
        else:
            counts["not found"] += 1
        if row["docstatus"] == 0:
            drafts.append((row["name"], values))
        else:
            new[row["name"]] = values
    bulk_update_rows(DOCTYPE, new)
    replace_changed_scans({n: s for n, s in scans.items() if n in new})
    for name, values in drafts:
        submit_draft(name, values, scans.get(name))
    return dict(counts)


def replace_changed_scans(scans_by_name: Dict[str, list]) -> int:
    """Replaces the scans only of the trackings whose scans changed (count or latest time).
    1 read, then 1 DELETE and 1 INSERT for each chunk of changed trackings."""
    names = [n for n, s in scans_by_name.items() if s]
    if not names:
        return 0
    table = frappe.qb.DocType(SCANS)
    current = {}
    for chunk in chunks(names):
        for parent, count, latest in (frappe.qb.from_(table).select(table.parent, Count("*"), Max(table.time))
                                      .where(table.parenttype == DOCTYPE).where(table.parent.isin(chunk))
                                      .groupby(table.parent).run()):
            current[parent] = (count, latest)
    changed = [n for n in names
               if current.get(n) != (len(scans_by_name[n]), max(s.time for s in scans_by_name[n]))]
    ts, user = now_datetime(), frappe.session.user
    for chunk in chunks(changed):
        frappe.qb.from_(table).delete().where(table.parenttype == DOCTYPE).where(table.parent.isin(chunk)).run()
        rows = [
            (frappe.generate_hash(length=10), ts, ts, user, user, 1, idx, parent, "scans", DOCTYPE,
             scan.time, scan.location, scan.status_detail)
            for parent in chunk for idx, scan in enumerate(scans_by_name[parent], start=1)
        ]
        bulk_insert_rows(SCANS, ("name", "creation", "modified", "owner", "modified_by", "docstatus", "idx", "parent",
                                 "parentfield", "parenttype", "time", "location", "status_detail"), rows)
    return len(changed)


def submit_draft(name: str, values: dict, scans: Optional[list]) -> None:
    """A draft with tracking data is submitted with its hooks. A failure is logged."""
    doc = frappe.get_doc(DOCTYPE, name)
    doc.update(values)
    if scans:
        doc.set("scans", [])
        for scan in scans:
            doc.append("scans", {"time": scan.time, "location": scan.location, "status_detail": scan.status_detail})
    frappe.db.savepoint("submit_draft")
    try:
        doc.submit()
    except Exception:
        # Undo only this draft, not the tracking data of the batch written before it
        frappe.db.rollback(save_point="submit_draft")
        frappe.local.message_log = []
        frappe.log_error(frappe.get_traceback(), f"Shipping: could not submit {name}")


def track_now(doc) -> TrackingResult:
    """The form button "Get Tracking": one tracking, now."""
    from .registry import require_carrier

    carrier = require_carrier(doc.carrier_name, "track")
    if not doc.awb_number or doc.awb_number in NO_AWB:
        frappe.throw("Book the shipment or enter the AWB Number first.")
    result = carrier.provider.track_many({doc.awb_number: doc.name})[doc.awb_number]
    row = {f: doc.get(f) for f in ("name", "awb_number", "docstatus") + RESULT_FIELDS}
    apply_tracking_results([row], {doc.awb_number: result}, source="Manual")
    record_unknown([carrier.provider.resolve])
    return result


# ------------------------------------------------------------------------------------ aggregator

def push_to_aggregator(settings: Optional[ShippingSettings] = None, now=None) -> Dict[str, int]:
    """Sends the new AWBs of Shipway carriers to Shipway. The same rules as the old
    `send_bulk_tracks`, in SQL: not pushed yet, last changed 2 to 19 days ago."""
    settings = settings or get_shipping_settings()
    today = getdate(now or nowdate())
    query, ct, _tpt, acc = base_query()
    rows = (
        query.select(ct.posted_to_shipway)
        .where(acc.provider == "Shipway")
        .where(ct.posted_to_shipway == 0)
        .where(ct.modified < add_days(today, -1))
        .where(ct.modified >= add_days(today, -(settings.shipway_push_max_days - 1)))
        .orderby(ct.creation, order=Order.desc)
    ).run(as_dict=True)
    carriers = get_carriers(r["carrier_name"] for r in rows)
    new, old, counts = {}, {}, defaultdict(int)
    for row in rows:
        carrier = carriers.get(row["carrier_name"])
        try:
            pushed = bool(carrier) and carrier.provider.push(row["name"], row["awb_number"], carrier.service_code)
        except ProviderError as e:
            frappe.log_error(str(e)[:1000], "Shipping: Shipway push failed")
            pushed = False
        counts["pushed" if pushed else "failed"] += 1
        if pushed:
            new[row["name"]] = {"posted_to_shipway": 1, "status": "Shipment Data Uploaded"}
            old[row["name"]] = {"posted_to_shipway": 0, "status": row.get("status")}
    bulk_set_fields(DOCTYPE, new, old, add_versions=False)
    return dict(counts)


# ----------------------------------------------------------------------------- unpublish, close

def unpublish_ctracks(settings: Optional[ShippingSettings] = None, now=None) -> None:
    """One UPDATE: a published tracking is unpublished when it was delivered more than
    `unpublish_after_delivery_days` ago, when its status is RTO, Cancelled, Closed or Not
    Booked, or when it is older than `published_ctrack_days`."""
    settings = settings or get_shipping_settings()
    now = get_datetime(now or now_datetime())
    ct = frappe.qb.DocType(DOCTYPE)
    (
        frappe.qb.update(ct)
        .set(ct.published, 0)
        .set(ct.route, "")
        .where(ct.published == 1)
        .where(
            ((ct.status == st.DELIVERED) & (ct.delivery_date_time <= now - timedelta(days=settings.unpublish_after_delivery_days)))
            | ct.status.isin(st.UNPUBLISH_AT_ONCE)
            | (ct.creation <= now - timedelta(days=settings.published_ctrack_days))
        )
    ).run()
    from frappe.website.render import clear_cache

    clear_cache()


def stale_query(settings: ShippingSettings, now=None, account: Optional[str] = None, count: bool = False):
    """The query of the open submitted trackings older than `ctrack_auto_close_days`,
    of one Shipping Provider Account when `account` is given."""
    now = get_datetime(now or now_datetime())
    query, ct, tpt, _acc = base_query(count=count)
    if account:
        query = query.where(tpt.shipping_provider_account == account)
    return (
        query.where(ct.docstatus == 1)
        .where(ct.status.isnull() | ct.status.notin(st.FINAL_STATUSES))
        .where(ct.creation < now - timedelta(days=settings.ctrack_auto_close_days))
    ), ct


def select_stale(settings: ShippingSettings, now=None, limit: Optional[int] = None,
                 account: Optional[str] = None) -> List[dict]:
    """Open submitted trackings older than `ctrack_auto_close_days`, oldest first."""
    query, ct = stale_query(settings, now, account)
    query = query.orderby(ct.creation)
    if limit:
        query = query.limit(limit)
    return query.run(as_dict=True)


def refresh_and_close_stale(limit: Optional[int] = None, settings: Optional[ShippingSettings] = None,
                            account: Optional[str] = None) -> Dict[str, int]:
    """Polls the stale open trackings once, then closes those still open as "Closed - No
    Update" and unpublishes them. The "Close Stale Trackings" button of a Shipping Provider
    Account runs it for that account (#169). For all accounts:
    bench --site <site> execute rigpl_erpnext.rigpl_erpnext.shipping.tracking.refresh_and_close_stale"""
    settings = settings or get_shipping_settings()
    rows = select_stale(settings, limit=limit, account=account)
    counts = track_rows(rows, source="Poll", commit=True)
    names = [r["name"] for r in rows]
    ct = frappe.qb.DocType(DOCTYPE)
    still_open = []
    for chunk in chunks(names):
        still_open += (frappe.qb.from_(ct).select(ct.name, ct.status, ct.published).where(ct.name.isin(chunk))
                       .where(ct.status.isnull() | ct.status.notin(st.FINAL_STATUSES)).run(as_dict=True))
    bulk_set_fields(
        DOCTYPE,
        {r["name"]: {"status": st.CLOSED, "published": 0} for r in still_open},
        {r["name"]: {"status": r["status"], "published": r["published"]} for r in still_open},
        add_versions=False,
    )
    add_comments([(r["name"], f"Closed - No Update by the stale clean-up (#169). Status before: {r['status'] or 'empty'}.")
                  for r in still_open])
    frappe.db.commit()
    counts["closed"] = len(still_open)
    message = f"Stale trackings: {len(rows)} checked. " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    print(message)
    if account:
        report_to_account(account, message)
    return dict(counts)


def add_comments(rows: List[Tuple[str, str]], doctype: str = DOCTYPE) -> None:
    """One Info Comment for each (document, text), so a bulk change can be undone by hand.
    Carrier Tracking does not track changes, so no Version is written. 1 INSERT per 1000,
    without the Comment hooks (a Comment insert with hooks costs about 20 queries)."""
    ts, user = now_datetime(), frappe.session.user
    comments = [(frappe.generate_hash(length=10), ts, ts, user, user, "Info", doctype, name, text)
                for name, text in rows]
    bulk_insert_rows("Comment", ("name", "creation", "modified", "owner", "modified_by", "comment_type",
                                 "reference_doctype", "reference_name", "content"), comments)


def report_to_account(account: str, message: str) -> None:
    """The result of an account job: a Comment on the account and a message to the user."""
    add_comments([(account, message)], doctype="Shipping Provider Account")
    frappe.db.commit()
    frappe.publish_realtime("msgprint", message, user=frappe.session.user)


# ------------------------------------------------------------------- re-apply the status map

# Final statuses are never changed by a re-apply: Delivered was confirmed, RTO and Cancelled
# and Not Booked were set by the carrier, a user or the booking. Closed may only become final.
SKIP_REAPPLY = (st.DELIVERED, st.RTO, st.CANCELLED, st.NOT_BOOKED)
CLOSED_MAY_BECOME = (st.DELIVERED, st.RTO)
SCANS_SQL = """
SELECT ct.name, ct.status, ct.status_code, ct.delivery_date_time, s.time AS scan_time, s.status_detail
FROM `tabCarrier Tracking` ct
JOIN `tabTransporters` tpt ON tpt.name = ct.carrier_name
JOIN `tabCourier Tracking Scans` s ON s.parent = ct.name AND s.parenttype = 'Carrier Tracking'
WHERE tpt.shipping_provider_account = %(account)s AND ct.docstatus = 1
    AND IFNULL(ct.status, '') NOT IN %(skip)s
ORDER BY ct.name, s.time, s.idx
"""


def stored_scans(account: str) -> Dict[str, List[dict]]:
    """{tracking: [scans, oldest first]} of the submitted trackings of the account that are
    not final: 1 query."""
    scans: Dict[str, List[dict]] = {}
    for row in frappe.db.sql(SCANS_SQL, {"account": account, "skip": SKIP_REAPPLY}, as_dict=True):
        scans.setdefault(row.name, []).append(row)
    return scans


def scan_code(status_detail: str) -> str:
    """"DLV: OTP Based Delivered-..." gives "DLV". Text with no "CODE:" gives ""."""
    head, sep, _rest = (status_detail or "").partition(":")
    head = head.strip()
    return head.upper() if sep and head and " " not in head and len(head) <= 20 else ""


def status_from_scans(scans: List[dict], resolve) -> Optional[Tuple[str, str, object]]:
    """(status, code, scan time) from the stored scans, or None. The scan times of old
    trackings are often out of order, so a Delivered scan anywhere wins, then an RTO scan,
    then the latest scan with a mapped code."""
    mapped = []
    for scan in scans:
        code = scan_code(scan["status_detail"])
        status = resolve(code, scan["status_detail"] or "")
        if status:
            mapped.append((status, code, scan["scan_time"]))
    for final in (st.DELIVERED, st.RTO):
        found = [m for m in mapped if m[0] == final]
        if found:
            return found[-1]
    return mapped[-1] if mapped else None


def plan_status_changes(scans_by_name: Dict[str, List[dict]], resolve) -> Dict[str, Tuple[str, dict]]:
    """Pure: {name: (old status, new values)} for the trackings whose scans map to another
    status. A tracking with no mapped scan is not changed."""
    changes = {}
    for name, scans in scans_by_name.items():
        head = scans[0]
        old = head["status"] or ""
        found = status_from_scans(scans, resolve)
        if not found or found[0] == old:
            continue
        new, code, scan_time = found
        if old == st.CLOSED and new not in CLOSED_MAY_BECOME:
            continue
        values = {"status": new, "status_code": code or head["status_code"]}
        if new == st.DELIVERED and not head["delivery_date_time"]:
            values["delivery_date_time"] = scan_time
        elif new != st.DELIVERED and head["delivery_date_time"]:
            values["delivery_date_time"] = None
        changes[name] = (old, values)
    return changes


def reapply_status_map(account: str, dry_run: bool = False) -> Dict[str, int]:
    """Works out the status of each open or closed tracking of the account again from its
    stored scans and the Shipping Status Map (see status_from_scans). No carrier API is
    called. Returns {"old -> new": count}."""
    from .status_map import StatusResolver

    provider = frappe.db.get_value("Shipping Provider Account", account, "provider")
    resolver = StatusResolver(provider)
    changes = plan_status_changes(stored_scans(account), resolver)
    counts = defaultdict(int)
    for old, values in changes.values():
        counts[f"{old or 'empty'} -> {values['status']}"] += 1
    if dry_run:
        return dict(counts)
    bulk_update_rows(DOCTYPE, {name: values for name, (_old, values) in changes.items()})
    add_comments([(name, f"Status from the stored scans (Re-apply Status Map): {old or 'empty'} -> "
                         f"{values['status']} ({values['status_code']})") for name, (old, values) in changes.items()])
    record_unknown([resolver])
    message = f"Re-apply Status Map of {account}: {len(changes)} trackings changed. " + \
        ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    report_to_account(account, message)
    return dict(counts)
