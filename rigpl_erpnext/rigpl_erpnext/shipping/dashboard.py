"""
The dashboard and the stale clean-up button of a Shipping Provider Account (#169).
"""
from typing import Dict

import frappe
from frappe.query_builder.functions import Avg, Count
from pypika.terms import CustomFunction
from frappe.utils import add_days, cint, flt, getdate

from . import status as st
from .settings import get_shipping_settings
from .tracking import stale_query

NO_STATUS = "No Status"
# MariaDB DATEDIFF(end, start). pypika DateDiff writes DATEDIFF(interval, start, end).
DATEDIFF = CustomFunction("DATEDIFF", ["end_date", "start_date"])
CLOSE_JOB = "rigpl_erpnext.rigpl_erpnext.shipping.tracking.refresh_and_close_stale"


@frappe.whitelist()
def get_account_summary(account, from_date, to_date) -> Dict:
    """The Carrier Trackings of the account made from `from_date` to `to_date`, by status,
    and the stale open trackings of all time. 2 queries."""
    frappe.has_permission("Shipping Provider Account", "read", account, throw=True)
    from_date, to_date = getdate(from_date), getdate(to_date)
    if from_date > to_date:
        frappe.throw("From Date must be on or before To Date.", title="Wrong Period")

    ct, tpt = frappe.qb.DocType("Carrier Tracking"), frappe.qb.DocType("Transporters")
    rows = (
        frappe.qb.from_(ct)
        .join(tpt).on(tpt.name == ct.carrier_name)
        .select(ct.status, Count("*").as_("count"), Avg(DATEDIFF(ct.delivery_date_time, ct.pickup_date)).as_("days"))
        .where(tpt.shipping_provider_account == account)
        .where(ct.docstatus < 2)
        .where(ct.creation >= from_date)
        .where(ct.creation < add_days(to_date, 1))
        .groupby(ct.status)
    ).run(as_dict=True)

    counts = {}
    avg_days = None
    for row in rows:
        status = row.status or NO_STATUS
        counts[status] = counts.get(status, 0) + cint(row.count)
        if status == st.DELIVERED and row.days is not None:
            avg_days = round(flt(row.days), 1)
    order = list(st.ALL_STATUSES) + [NO_STATUS]
    by_status = [{"status": s, "count": counts[s]} for s in sorted(counts, key=lambda s: order.index(s) if s in order else len(order))]

    settings = get_shipping_settings()
    stale = stale_query(settings, account=account, count=True)[0].run(as_dict=True)
    return {
        "total": sum(counts.values()),
        "by_status": by_status,
        "avg_transit_days": avg_days,
        "stale_open": cint(stale[0]["count"]) if stale else 0,
        "auto_close_days": settings.ctrack_auto_close_days,
    }


def close_job_name(account: str) -> str:
    return f"close_stale:{account}"


@frappe.whitelist()
def close_stale_trackings(account) -> str:
    """Starts the stale clean-up of the account in the long queue, once at a time."""
    frappe.has_permission("Shipping Provider Account", "write", account, throw=True)
    from frappe.utils.background_jobs import get_jobs

    job_name = close_job_name(account)
    site = frappe.local.site
    if job_name in get_jobs(site=site, queue="long", key="job_name").get(site, []):
        frappe.throw(f"The stale clean-up of {account} is already queued or running.", title="Already Running")
    frappe.enqueue(CLOSE_JOB, queue="long", timeout=3600, job_name=job_name, account=account)
    return f"The stale clean-up of {account} has started. You get a message when it ends."
