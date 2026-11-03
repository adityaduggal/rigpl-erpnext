# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import add_days, flt

from ...utils.item_attribute_utils import get_attribute_map
from ...utils.other_utils import round_down


def validate(doc, method):
    create_valuation_rate(doc)
    po_grn_validations(doc)
    msme_pterms_validations(doc)


def msme_pterms_validations(doc):
    if not doc.bill_no:
        frappe.throw("Supplier Invoice No is Mandatory for {}".format(doc.name))

    sup_doc = frappe.get_doc("Supplier", doc.supplier)
    if not sup_doc.payment_terms:
        frappe.throw("Payment Terms not Mentioned in Supplier {} for PI# {}".format(doc.supplier, doc.name))

    if sup_doc.is_msme_registered == 1:
        days_to_add = frappe.get_value("Payment Terms Template", sup_doc.payment_terms, "days_to_add_in_pi")
        if doc.posting_date < add_days(doc.bill_date, flt(days_to_add)):
            frappe.throw("Not Allowed, Posting Date = {} and Supplier Invoice Date = {}. Total Difference "
                         "should be Greater than {} days".format(doc.posting_date, doc.bill_date, days_to_add))


def po_grn_validations(doc):
    pass


def create_valuation_rate(doc):
    # This function would create/update the valuation rate for the Carbide Cut Pieces
    # Check if the GRN is for Carbide Raw Material
    for row in doc.items:
        if frappe.db.get_value("Purchase Order", row.purchase_order, "is_subcontracting") == 1:
            continue
        item = frappe.db.get_value("Item", row.item_code, ["name", "variant_of", "is_stock_item"], as_dict=1)
        if not item or not item.variant_of or item.is_stock_item != 1:
            continue
        atts = get_attribute_map([item.name]).get(item.name, {})
        if atts.get("Tool Type") != "Round Tool Bits" or "l1_mm" not in atts:
            continue
        for var in get_cut_pieces(item.variant_of, atts.get("d1_mm"), atts["l1_mm"], row.base_net_rate):
            frappe.db.set_value("Item", var["name"], {"valuation_rate": var["valuation"],
                "valuation_rate_date": doc.posting_date})
            frappe.msgprint('Updated Valuation Rate #{0} for Item Code: {1} with Date: '
                            '{2}'.format(var["valuation"], var["name"], str(doc.posting_date)))


def get_cut_pieces(template, diameter, length, rate):
    """Variants of the template with the same d1_mm, with a valuation rate by their l1_mm, sorted by
    length. The d1_mm compares as a number, as the old SQL did."""
    if diameter is None:
        return []
    it = frappe.qb.DocType("Item")
    iva = frappe.qb.DocType("Item Variant Attribute")
    rows = (
        frappe.qb.from_(it)
        .join(iva).on(iva.parent == it.name)
        .select(it.name, iva.attribute_value)
        .where((it.variant_of == template) & (iva.attribute == "d1_mm"))
        .run()
    )
    similar = [name for name, value in rows if value is not None and flt(value) == flt(diameter)]
    lengths = get_attribute_map(similar, ["l1_mm"])
    vr_list = []
    for name in similar:
        var_length = lengths.get(name, {}).get("l1_mm")
        if var_length is None:
            continue
        ratio = flt(var_length) / flt(length)
        if ratio < 0.5:
            factor = 0.8
        elif ratio < 0.9:
            factor = 0.9
        else:
            factor = 1
        vr_list.append({"name": name, "length": var_length,
            "valuation": round_down(flt(rate) * ratio * factor, 10)})
    return sorted(vr_list, key=lambda k: k["length"])
