"""
The Carrier Tracking form actions on the provider layer (#168): book, cancel, labels, rates,
serviceability and proof of delivery. Each action is for one document, so it may use
get_doc and save.
"""
from typing import List

import frappe
from frappe.utils import cint, flt
from frappe.utils.file_manager import remove_all, save_file

from .base import Label, NotSupported, ProviderError
from .registry import require_carrier
from .request import build_shipment_request
from . import status as st

NO_AWB = ("", "NA")


def provider_error(e: Exception, action: str):
    frappe.throw(str(e), title=f"Shipping: {action} failed")


def save_labels(doc, labels: List[Label]) -> List[str]:
    return [save_file(label.filename, label.content, doc.doctype, doc.name, is_private=1).file_url for label in labels]


def get_rates(doc) -> None:
    from ..doctype.carrier_tracking.common import get_shipment_cost

    if cint(frappe.db.get_value("Transporters", doc.carrier_name, "calculate_cost_from_quote")):
        doc.shipment_cost = get_shipment_cost(doc)
        return
    carrier = require_carrier(doc.carrier_name, "rate")
    try:
        rates = carrier.provider.get_rates(build_shipment_request(doc, carrier.service_code))
    except (ProviderError, NotSupported) as e:
        provider_error(e, "Rates")
    rate = next((r for r in rates if r.service_code == carrier.service_code), rates[0] if rates else None)
    if not rate:
        frappe.throw(f"{carrier.provider.name} gave no rate for {doc.name}")
    if rate.oda and not doc.allow_oda_shipment:
        frappe.throw(f"{doc.name}: the destination is out of the delivery area (ODA) of {carrier.provider.name}. "
                     "Check Allow ODA Shipment to book it.", title="ODA Shipment")
    doc.shipment_cost = rate.amount
    doc.shipment_cost_currency = rate.currency or doc.shipment_cost_currency
    if rate.delivery_date:
        doc.expected_delivery_date = rate.delivery_date
    frappe.msgprint(f"{carrier.provider.name} {rate.service_code}: {rate.currency} {rate.amount}"
                    + (f", {rate.transit_days} days" if rate.transit_days else "")
                    + (f", delivery by {rate.delivery_date}" if rate.delivery_date else ""))


def check_serviceability(doc, cod: bool = False) -> str:
    carrier = require_carrier(doc.carrier_name, "serviceability")
    req = build_shipment_request(doc, carrier.service_code)
    try:
        ok, message = carrier.provider.check_serviceability(req.origin, req.destination, cod)
    except ProviderError as e:
        provider_error(e, "Serviceability")
    if not ok:
        frappe.throw(message, title="No Service")
    return message


def book(doc, test_marking: bool = False) -> None:
    """Books the shipment, saves the labels and submits the tracking."""
    carrier = require_carrier(doc.carrier_name, "book", booking=True)
    if doc.get("__islocal"):
        frappe.throw("Save the Carrier Tracking before you book the shipment.")
    if not doc.shipment_package_details:
        frappe.throw(f"Package Details are needed to book {doc.name}.")
    if doc.awb_number and doc.awb_number not in NO_AWB:
        frappe.throw(f"{doc.name} is already booked with AWB {doc.awb_number}.")
    if carrier.provider.supports("serviceability") and carrier.provider.check_service_before_booking:
        check_serviceability(doc)
    if carrier.provider.supports("rate") or cint(
            frappe.db.get_value("Transporters", doc.carrier_name, "calculate_cost_from_quote")):
        get_rates(doc)
    try:
        result = carrier.provider.book(build_shipment_request(doc, carrier.service_code, test_marking=test_marking))
    except (ProviderError, NotSupported) as e:
        provider_error(e, "Booking")
    doc.awb_number = result.awb
    doc.status = st.BOOKED
    doc.tracking_source = "Manual"
    if result.cost is not None:
        doc.shipment_cost = result.cost
    for row, package_id in zip(doc.shipment_package_details, result.package_ids):
        row.tracking_id = package_id
    save_labels(doc, result.labels)
    doc.flags.ignore_permissions = True
    doc.submit() if doc.docstatus == 0 else doc.save()
    frappe.msgprint(f"Booked {doc.name} with {carrier.provider.name} AWB {result.awb}"
                    + (" (TEST booking: cancel it)" if test_marking else ""))


def validate_address(doc) -> None:
    carrier = require_carrier(doc.carrier_name, "address")
    address = build_shipment_request(doc, carrier.service_code).destination
    try:
        frappe.msgprint(carrier.provider.validate_address(address))
    except (ProviderError, NotSupported) as e:
        provider_error(e, "Address check")


def get_labels(doc) -> None:
    carrier = require_carrier(doc.carrier_name, "label")
    try:
        urls = save_labels(doc, carrier.provider.get_labels(doc.awb_number))
    except (ProviderError, NotSupported) as e:
        provider_error(e, "Label")
    frappe.msgprint(f"{len(urls)} label(s) attached to {doc.name}")


def get_pod(doc) -> None:
    from .pod import fetch_pod_now

    fetch_pod_now(doc)


def cancel(doc) -> None:
    """Cancels the booking with the carrier when it can, then makes the tracking a draft
    again with no AWB, so it can be booked again (as the old Delete Shipment did)."""
    if doc.status != st.BOOKED:
        frappe.throw(f"Only Booked shipments can be cancelled. {doc.name} is {doc.status}.")
    carrier = require_carrier(doc.carrier_name, "track")
    if carrier.provider.supports("cancel"):
        try:
            carrier.provider.cancel(doc.awb_number)
        except ProviderError as e:
            provider_error(e, "Cancel")
    else:
        frappe.msgprint(f"{carrier.provider.name} has no cancel API. Cancel AWB {doc.awb_number} on the carrier portal.")
    frappe.db.set_value(doc.doctype, doc.name, {"docstatus": 0, "awb_number": "NA", "status_code": "", "published": 0,
                                                "route": "", "status": st.NOT_BOOKED})
    pkg = frappe.qb.DocType("Shipment Package Details")
    (frappe.qb.update(pkg).set(pkg.docstatus, 0).set(pkg.tracking_id, "")
     .where(pkg.parent == doc.name).where(pkg.parenttype == doc.doctype)).run()
    remove_all(doc.doctype, doc.name)
    if doc.document == "Sales Invoice":
        frappe.db.set_value("Sales Invoice", doc.document_name, {"transporters": doc.carrier_name, "lr_no": "NA"})
