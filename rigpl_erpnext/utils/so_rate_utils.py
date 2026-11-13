"""
The Sales Order is the only source of rates for the Delivery Note and the Sales Invoice (#223).
A row with a Sales Order Item gets the price fields of that item, whatever ERPNext or the user did to the rate.
"""
import frappe
from frappe.utils import flt

SO_PRICE_FIELDS = ["rate", "price_list_rate", "discount_percentage", "discount_amount", "margin_type",
    "margin_rate_or_amount", "rate_with_margin", "pricing_rules"]
TEXT_FIELDS = ("margin_type", "pricing_rules")
RATE_TOLERANCE = 0.01


def copy_so_rates(doc):
    """Overwrites the price fields of each row with a Sales Order Item, redoes the totals and names the changed rows"""
    rows = [d for d in doc.get("items") if d.get("so_detail")]
    if doc.get("is_return") or not rows:
        return
    so_rows = {d.name: d for d in frappe.get_all("Sales Order Item",
        filters={"name": ("in", list({d.so_detail for d in rows}))}, fields=["name"] + SO_PRICE_FIELDS)}
    changed = []
    for row in rows:
        so_row = so_rows.get(row.so_detail)
        if so_row and set_price_fields(row, so_row):
            changed.append(row.idx)
    if changed:
        doc.calculate_taxes_and_totals()
        frappe.msgprint("Rates of Row# {} are set from the Sales Order. The Sales Order is the only source of "
            "rates.".format(", ".join(str(idx) for idx in changed)), title="Rates Changed", indicator="orange")


def set_price_fields(row, so_row):
    """Returns True if any field of the row differs from the Sales Order Item and is set to its value"""
    changed = False
    for field in SO_PRICE_FIELDS:
        if differs(field, row.get(field), so_row.get(field)):
            setattr(row, field, so_row.get(field))
            changed = True
    return changed


def differs(field, value, so_value):
    if field in TEXT_FIELDS:
        return (value or "") != (so_value or "")
    return abs(flt(value) - flt(so_value)) >= 1e-6


def check_dn_rates_match_so(doc):
    """No role can invoice a Delivery Note row whose rate is not the rate of its Sales Order Item"""
    from rigpl_erpnext.utils.sales_utils import get_rows_error_table
    rows = [d for d in doc.get("items") if d.get("so_detail") and d.get("dn_detail")]
    if doc.get("is_return") or not rows:
        return
    so_rates = get_rates("Sales Order Item", {d.so_detail for d in rows})
    dn_rates = get_rates("Delivery Note Item", {d.dn_detail for d in rows})
    errors = [(row, "SO rate {} / DN rate {}".format(so_rates[row.so_detail], dn_rates[row.dn_detail]))
        for row in rows if row.so_detail in so_rates and row.dn_detail in dn_rates
        and abs(dn_rates[row.dn_detail] - so_rates[row.so_detail]) >= RATE_TOLERANCE]
    if errors:
        frappe.throw(get_rows_error_table(doc, errors) + "<br>The Delivery Note must have the rate of the Sales "
            "Order. Correct or cancel the Delivery Note first.", title="Delivery Note Rate Not Same as Sales Order")


def get_rates(doctype, names):
    return {d.name: flt(d.rate) for d in frappe.get_all(doctype, filters={"name": ("in", list(names))},
        fields=["name", "rate"])}


def ignore_pricing_rule_for_so_rows(doc):
    """ERPNext prices a row again on save when the flag is 0. All rows from Sales Orders need no pricing"""
    items = doc.get("items")
    if items and not doc.get("is_return") and all(d.get("so_detail") for d in items):
        doc.ignore_pricing_rule = 1
