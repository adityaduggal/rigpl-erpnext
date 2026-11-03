"""
Proof of delivery (#171). A POD is fetched when a tracking becomes Delivered, and again each
day for the Delivered trackings of the last POD_RETRY_DAYS that have no POD yet. The form
button uses the same code. Only providers with the "pod" capability are asked (FedEx now).
"""
from typing import Dict, Iterable, List, Tuple

import frappe
from frappe.utils import add_days, nowdate
from frappe.utils.file_manager import save_file

from ...utils.batch_write_utils import bulk_update_rows
from . import status as st
from .base import NotSupported, ProviderError
from .registry import get_carriers, provider_classes

DOCTYPE = "Carrier Tracking"
POD_RETRY_DAYS = 30
POD_RETRY_LIMIT = 200
COMMIT_EVERY = 25
FETCH_JOB = "rigpl_erpnext.rigpl_erpnext.shipping.pod.fetch_pods"


def pod_providers() -> List[str]:
    return sorted(name for name, cls in provider_classes().items() if "pod" in cls.capabilities)


def needs_pod(row: dict, new_status: str) -> bool:
    """True when this result makes the tracking Delivered and its provider can give a POD."""
    return (new_status == st.DELIVERED and row.get("status") != st.DELIVERED and not row.get("pod_file")
            and row.get("provider") in pod_providers())


def queue_pods(names: List[str]) -> None:
    """One job for the names, after the commit that makes them Delivered."""
    if names:
        frappe.enqueue(FETCH_JOB, queue="long", timeout=1800, enqueue_after_commit=True, names=names)


def pending_query():
    """Delivered submitted trackings with an AWB and no POD."""
    ct = frappe.qb.DocType(DOCTYPE)
    query = (
        frappe.qb.from_(ct)
        .select(ct.name, ct.awb_number, ct.carrier_name)
        .where(ct.docstatus == 1)
        .where(ct.status == st.DELIVERED)
        .where(ct.awb_number.notnull())
        .where(ct.awb_number.notin(("", "NA")))
        .where(ct.pod_file.isnull() | (ct.pod_file == ""))
    )
    return query, ct


def fetch_pods(names: List[str]) -> Dict[str, int]:
    """The background job: fetches the POD of each of `names` that still needs one. Errors
    are counted and written to one Error Log for the run."""
    query, ct = pending_query()
    rows = query.where(ct.name.isin(list(names))).run(as_dict=True) if names else []
    return fetch_rows(rows, commit=True)


def retry_missing_pods() -> Dict[str, int]:
    """Daily: the Delivered trackings of the last POD_RETRY_DAYS with no POD, oldest first."""
    providers = pod_providers()
    if not providers:
        return {}
    query, ct = pending_query()
    tpt, acc = frappe.qb.DocType("Transporters"), frappe.qb.DocType("Shipping Provider Account")
    rows = (
        query.join(tpt).on(tpt.name == ct.carrier_name)
        .join(acc).on(acc.name == tpt.shipping_provider_account)
        .where(acc.enabled == 1)
        .where(acc.provider.isin(providers))
        .where(ct.delivery_date_time >= add_days(nowdate(), -POD_RETRY_DAYS))
        .orderby(ct.delivery_date_time)
        .limit(POD_RETRY_LIMIT)
    ).run(as_dict=True)
    return fetch_rows(rows, commit=True)


def fetch_rows(rows: List[dict], commit: bool) -> Dict[str, int]:
    carriers = get_carriers(r["carrier_name"] for r in rows) if rows else {}
    values, errors = {}, []
    for chunk in chunks_of(rows, COMMIT_EVERY):
        chunk_values, chunk_errors = download(chunk, carriers)
        bulk_update_rows(DOCTYPE, chunk_values)
        values.update(chunk_values)
        errors += chunk_errors
        if commit:
            frappe.db.commit()
    if errors:
        frappe.log_error("\n".join(errors)[:10000], f"Shipping: {len(errors)} proof of delivery fetches failed")
    return {"fetched": len(values), "failed": len(errors)}


def download(rows: List[dict], carriers: Dict) -> Tuple[Dict[str, Dict], List[str]]:
    """({name: {"pod_file": url}}, ["name: error"]). One provider call and one File for each row."""
    values, errors = {}, []
    for row in rows:
        carrier = carriers.get(row["carrier_name"])
        if not carrier or not carrier.provider.supports("pod"):
            continue
        try:
            label = carrier.provider.get_pod(row["awb_number"])
        except (ProviderError, NotSupported) as e:
            errors.append(f"{row['name']}: {e}")
            continue
        url = save_file(label.filename, label.content, DOCTYPE, row["name"], is_private=1).file_url
        values[row["name"]] = {"pod_file": url}
    return values, errors


def fetch_pod_now(doc) -> str:
    """The form button: fetches the POD of one tracking now and shows any error to the user."""
    from .registry import require_carrier

    carrier = require_carrier(doc.carrier_name, "pod")
    if doc.status != st.DELIVERED:
        frappe.throw(f"{doc.name} is not delivered yet.")
    try:
        label = carrier.provider.get_pod(doc.awb_number)
    except (ProviderError, NotSupported) as e:
        frappe.throw(str(e), title="Shipping: Proof of delivery failed")
    url = save_file(label.filename, label.content, DOCTYPE, doc.name, is_private=1).file_url
    frappe.db.set_value(DOCTYPE, doc.name, "pod_file", url)
    return url


def chunks_of(rows: List[dict], size: int) -> Iterable[List[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start:start + size]
