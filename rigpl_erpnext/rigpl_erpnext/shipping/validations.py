"""Carrier Tracking checks that do not call a carrier (moved from the old jobs module, #168)."""
import frappe
from frappe.utils import flt


def courier_charges_validation(ct_doc, max_percent_of_invoice_value, backend: bool = False) -> int:
    """1 when the courier cost is over the allowed percent of the invoice value and the
    courier is not charged enough. On a SOLD Sales Invoice this stops the save, unless
    `bypass_courier_charged_check` is set or `backend` is true."""
    if max_percent_of_invoice_value is None or ct_doc.shipment_cost is None or flt(ct_doc.amount) <= 0:
        return 0
    if flt(ct_doc.shipment_cost) / flt(ct_doc.amount) * 100 <= flt(max_percent_of_invoice_value):
        return 0
    sold_invoice = ct_doc.purpose == "SOLD" and ct_doc.document == "Sales Invoice"
    if not sold_invoice:
        if ct_doc.purpose != "SOLD" and ct_doc.document != "Sales Invoice":
            frappe.msgprint(f"Permissible Courier Cost is High. Make sure you charge courier for Minimum Amount of "
                            f"{ct_doc.shipment_cost}", title="Warning From Admin")
        return 0
    if flt(ct_doc.courier_charged) < flt(ct_doc.shipment_cost) and not ct_doc.bypass_courier_charged_check:
        if not backend:
            frappe.throw(f"Not Allowed. Courier Charged in Invoice {ct_doc.document_name} is Lower than Cost of ₹ "
                         f"{ct_doc.shipment_cost} for {ct_doc.name}", title="Courier Charges Too Low")
        return 1
    return 0
