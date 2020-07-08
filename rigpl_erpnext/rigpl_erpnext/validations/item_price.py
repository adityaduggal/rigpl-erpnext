# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import math
from frappe.utils import flt


def validate(doc, method):
    pl_doc = frappe.get_doc("Price List", doc.price_list)
    if pl_doc.price_round_type == 'CEILING':
        new_price = math.ceil(flt(doc.price_list_rate) / flt(pl_doc.rounding_multiple)) * pl_doc.rounding_multiple
    elif pl_doc.price_round_type == 'MROUND':
        new_price = round(flt(doc.price_list_rate) / flt(pl_doc.rounding_multiple)) * pl_doc.rounding_multiple

    else:
        new_price = doc.price_list_rate
    doc.price_list_rate = new_price
