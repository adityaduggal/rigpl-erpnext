# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import math
from frappe.utils import flt
from ..scheduled_tasks.item_valuation_rate import selling_item_valuation_rate_variant


def validate(doc, method):
    pl_doc = frappe.get_doc("Price List", doc.price_list)
    if pl_doc.price_round_type == 'CEILING':
        new_price = math.ceil(flt(doc.price_list_rate) / flt(pl_doc.rounding_multiple)) * pl_doc.rounding_multiple
    elif pl_doc.price_round_type == 'MROUND':
        new_price = round(flt(doc.price_list_rate) / flt(pl_doc.rounding_multiple)) * pl_doc.rounding_multiple

    else:
        new_price = doc.price_list_rate
    doc.price_list_rate = new_price


def on_update(doc,method):
    update_item_valuation_rate(doc)


def update_item_valuation_rate(doc):
    # Update the Item Valuation if needed
    if doc.selling == 1:
        itd = frappe.get_doc("Item", doc.item_code)
        if itd.variant_of:
            tempd = frappe.get_doc("Item", itd.variant_of)
            selling_item_valuation_rate_variant(itd, tempd)
