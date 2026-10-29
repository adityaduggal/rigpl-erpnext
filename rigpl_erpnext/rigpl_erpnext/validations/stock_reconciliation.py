# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import flt


def validate(doc, method):
    """
    Sets the Valuation Rate of each row unless Manual Rate is set. The stock already in the
    warehouse keeps its book rate and only the extra qty gets the Item master rate, then the
    Warehouse valuation rule is applied (#155).
    """
    item_vr = {
        d.name: flt(d.valuation_rate)
        for d in frappe.get_all(
            "Item", filters={"name": ["in", list({d.item_code for d in doc.items})]},
            fields=["name", "valuation_rate"],
        )
    }
    wh_rules = {
        d.name: d
        for d in frappe.get_all(
            "Warehouse", filters={"name": ["in", list({d.warehouse for d in doc.items})]},
            fields=["name", "valuation_rule", "valuation_rule_value"],
        )
    }
    for d in doc.items:
        if d.manual_valuation_rate:
            continue
        rate = get_book_rate(d, item_vr.get(d.item_code) or 1)
        d.valuation_rate = apply_warehouse_rule(rate, wh_rules.get(d.warehouse))
    doc.set_total_qty_and_amount()
    doc.difference_amount = sum(flt(d.amount_difference) for d in doc.items)


def get_book_rate(row, item_vr):
    """
    Returns the rate that keeps the current stock at its current valuation rate and values
    only the qty above the current qty at the Item master rate
    """
    cur_qty = max(flt(row.current_qty), 0)
    qty = flt(row.qty)
    if cur_qty == 0 or flt(row.current_valuation_rate) <= 0:
        return item_vr
    if qty <= cur_qty:
        return flt(row.current_valuation_rate)
    return (cur_qty * flt(row.current_valuation_rate) + (qty - cur_qty) * item_vr) / qty


def apply_warehouse_rule(rate, wh_rule):
    if not wh_rule or not wh_rule.valuation_rule:
        return rate
    if wh_rule.valuation_rule == "Fixed Rate":
        return flt(wh_rule.valuation_rule_value)
    return custom_round(rate * flt(wh_rule.valuation_rule_value) / 100)


def custom_round(number):
    if number < 100:
        return int(number)
    elif number < 500:
        return int(number / 5) * 5
    elif number < 1000:
        return int(number / 10) * 10
    elif number < 5000:
        return int(number / 50) * 50
    else:
        return int(number / 100) * 100
