"""
Which shipment buttons a Carrier Tracking shows (#173). The form gets the list in `__onload`,
and each button method checks it again on the server, so a stale form cannot run a wrong action.
"""
from typing import Dict, FrozenSet, List

import frappe
from frappe.utils import cint

from . import status as st
from .accounts import BOOKING, TRACKING_ONLY
from .actions import NO_AWB
from .registry import provider_classes, transporter_api

LABELS = {
    "get_rates": "Get Rates",
    "book_shipment": "Book Shipment",
    "address_validation": "Validate Address",
    "available_services": "Available Services",
    "get_labels": "Get Label",
    "get_status": "Get Status",
    "pushdata": "Post to Shipway",
    "get_pod": "Get Proof of Delivery",
    "delete_shipment": "Delete Shipment",
}
# A tracking with one of these statuses is booked, even with no AWB
SHIPPED = (st.BOOKED, st.IN_TRANSIT, st.OUT_FOR_DELIVERY, st.DELIVERED, st.RTO)
# A label is printed before the carrier picks up the shipment
BEFORE_PICKUP = ("", st.BOOKED, "Pickup Scheduled", "Shipment Data Uploaded")
STATE_FIELDS = ("carrier_name", "docstatus", "status", "awb_number", "pod_file", "posted_to_shipway")


def allowed_actions(docstatus: int, status: str, has_awb: bool, has_pod: bool, posted_to_shipway: bool,
                    api_mode: str, capabilities: FrozenSet[str], cost_from_quote: bool) -> List[str]:
    """The button methods allowed for a tracking in this state, in the order of LABELS."""
    if docstatus == 2:
        return []
    not_booked = not has_awb and status not in SHIPPED
    open_shipment = has_awb and status not in st.FINAL_STATUSES
    rules = {
        "get_rates": docstatus == 0 and not_booked and ("rate" in capabilities or cost_from_quote),
        "book_shipment": docstatus == 0 and not_booked and api_mode == BOOKING and "book" in capabilities,
        "address_validation": not_booked and "address" in capabilities,
        "available_services": not_booked and "serviceability" in capabilities,
        "get_labels": has_awb and status in BEFORE_PICKUP and "label" in capabilities,
        "get_status": open_shipment and api_mode in (BOOKING, TRACKING_ONLY) and "track" in capabilities,
        "pushdata": open_shipment and not posted_to_shipway and "push" in capabilities,
        "get_pod": has_awb and status == st.DELIVERED and not has_pod and "pod" in capabilities,
        "delete_shipment": docstatus == 1 and has_awb and status == st.BOOKED and api_mode == BOOKING,
    }
    return [action for action in LABELS if rules[action]]


def doc_actions(doc) -> List[str]:
    """allowed_actions for a Carrier Tracking. Reads only cached values."""
    provider, api_mode = transporter_api(doc.carrier_name)
    provider_class = provider_classes().get(provider)
    cost_from_quote = bool(doc.carrier_name) and cint(
        frappe.get_cached_value("Transporters", doc.carrier_name, "calculate_cost_from_quote"))
    return allowed_actions(
        docstatus=cint(doc.docstatus),
        status=doc.status or "",
        has_awb=(doc.awb_number or "") not in NO_AWB,
        has_pod=bool(doc.pod_file),
        posted_to_shipway=bool(cint(doc.posted_to_shipway)),
        api_mode=api_mode,
        capabilities=provider_class.capabilities if provider_class else frozenset(),
        cost_from_quote=bool(cost_from_quote),
    )


def check_action(doc, action: str) -> None:
    """Throws when `action` is not allowed. The state is read from the database: the form sends
    its own copy of the document, which the user can change."""
    saved = frappe.db.get_value(doc.doctype, doc.name, list(STATE_FIELDS), as_dict=True) if doc.name else None
    if not saved:
        frappe.throw(f"Save {doc.doctype} {doc.name or ''} before you use {LABELS[action]}.", title="Not Saved")
    if action not in doc_actions(saved):
        frappe.throw(f"{LABELS[action]} is not available for {doc.name} with status {saved.status or 'not set'} "
                     f"and AWB {saved.awb_number or 'not set'}.", title="Action Not Available")


def onload_actions(doc) -> Dict[str, str]:
    """{method: label} for the form buttons."""
    return {action: LABELS[action] for action in doc_actions(doc)}
