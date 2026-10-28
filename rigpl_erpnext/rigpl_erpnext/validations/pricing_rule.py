# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import flt


def validate(doc, method):
    if not doc.priority:
        doc.priority = 1
    # Same as v14 PricingRule.validate_mandatory; used by overrides.pricing_rule_utils
    doc.has_priority = 1
    if doc.apply_on == 'Attributes':
        doc.items = []
        doc.item_groups = []
        doc.brands = []
        for att in doc.attributes:
            att_doc = frappe.get_doc('Item Attribute', att.attribute)
            att.is_numeric = att_doc.numeric_values
        doc.buying = 1
        doc.selling = 0
        doc.applicable_for = 'Supplier'
        if not doc.supplier:
            frappe.throw("Supplier is Mandatory for Attribute based Pricing Rule")
        doc.rate_or_discount = 'Rate'
        if doc.rate == 0 or not doc.rate:
            frappe.throw("Rate is Mandatory for Attribute Based Pricing Rule")
    elif doc.apply_on == "Item Code":
        doc.attribute = []
        doc.item_groups = []
        doc.brands = []
        for it in doc.items:
            if not it.uom:
                it.uom = frappe.get_value("Item", it.item_code, "stock_uom")
    elif doc.apply_on == "Item Group":
        doc.attribute = []
        doc.items = []
        doc.brands = []
        for it in doc.item_groups:
            if not it.uom:
                it.uom = "Nos"
    else:
        frappe.msgprint(f"For Pricing Rule {doc.name} Blocked {doc.apply_on}")
    if doc.for_price_list:
        doc.currency = frappe.get_value("Price List", doc.for_price_list, "currency")
    if doc.rate_or_discount:
        if doc.margin_type:
            doc.margin_type = ""
        if doc.margin_rate_or_amount > 0:
            doc.marging_rate_or_amount = 0
    validate_amount_bands(doc)


def validate_amount_bands(doc):
    """
    MOV rules are amount bands on Item Codes (for example 58% up to one amount and 60% above
    the next). A line whose amount falls between two bands gets no MOV rule and drops back to
    the Item Group discount without any message, so stop gaps and same-priority overlaps here.
    """
    if doc.apply_on != "Item Code" or doc.disable or doc.price_or_product_discount != "Price":
        return
    if not (flt(doc.min_amt) or flt(doc.max_amt)):
        return

    bands_by_item = {}
    for row in get_amount_band_rules(doc):
        bands_by_item.setdefault(row.item_code, []).append(row)

    errors = []
    for it in doc.items:
        this_band = frappe._dict(name=doc.name, item_code=it.item_code, min_amt=doc.min_amt,
                                 max_amt=doc.max_amt, priority=doc.priority)
        for low, high, msg in find_amount_band_errors(bands_by_item.get(it.item_code, []) + [this_band]):
            if doc.name in (low, high) and msg not in errors:
                errors.append(msg)
    if errors:
        frappe.throw("<br>".join(errors), title="Pricing Rule Amount Band Gap")


def get_amount_band_rules(doc):
    """Other enabled amount-band rules for the same items, parties, price list and dates."""
    item_codes = [it.item_code for it in doc.items if it.item_code]
    if not item_codes:
        return []
    pr = frappe.qb.DocType("Pricing Rule")
    pri = frappe.qb.DocType("Pricing Rule Item Code")
    query = (
        frappe.qb.from_(pr)
        .join(pri).on(pri.parent == pr.name)
        .select(pr.name, pri.item_code, pr.min_amt, pr.max_amt, pr.priority)
        .distinct()
        .where(pri.item_code.isin(item_codes))
        .where(pr.name != doc.name)
        .where(pr.disable == 0)
        .where(pr.apply_on == "Item Code")
        .where(pr.price_or_product_discount == "Price")
        .where((pr.min_amt > 0) | (pr.max_amt > 0))
        .where(pr.selling == doc.selling)
        .where(pr.buying == doc.buying)
        .where(IfNull(pr.company, "") == (doc.company or ""))
        .where(IfNull(pr.currency, "") == (doc.currency or ""))
        .where(IfNull(pr.for_price_list, "") == (doc.for_price_list or ""))
        .where(IfNull(pr.applicable_for, "") == (doc.applicable_for or ""))
    )
    if doc.applicable_for:
        party_field = frappe.scrub(doc.applicable_for)
        query = query.where(IfNull(pr[party_field], "") == (doc.get(party_field) or ""))
    if doc.valid_upto:
        query = query.where(IfNull(pr.valid_from, "2000-01-01") <= doc.valid_upto)
    if doc.valid_from:
        query = query.where(IfNull(pr.valid_upto, "2099-12-31") >= doc.valid_from)
    return query.run(as_dict=True)


def find_amount_band_errors(bands):
    """
    Return (lower rule, higher rule, message) for each gap or same-priority overlap between
    neighbouring bands of one item. max_amt of 0 means the band has no upper limit.
    """
    errors = []
    bands = sorted(bands, key=lambda b: flt(b.min_amt))
    for low, high in zip(bands, bands[1:]):
        low_max, high_min = flt(low.max_amt), flt(high.min_amt)
        if (not low_max or high_min <= low_max) and str(low.priority) == str(high.priority):
            errors.append((low.name, high.name,
                f"Pricing Rule {low.name} (up to {low_max:,.0f}) and {high.name} (from "
                f"{high_min:,.0f}) overlap at the same priority {low.priority}. Change the "
                f"amounts or the priority."))
        elif low_max and high_min > low_max + 1:
            errors.append((low.name, high.name,
                f"Pricing Rule {low.name} ends at {low_max:,.0f} and {high.name} starts at "
                f"{high_min:,.0f}. Lines from {low_max + 1:,.0f} to {high_min - 1:,.0f} get "
                f"neither rule. Set Max Amount of {low.name} to {high_min - 1:,.0f}."))
    return errors
