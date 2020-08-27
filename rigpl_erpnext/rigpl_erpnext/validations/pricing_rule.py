# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
    if doc.apply_on == 'Attributes':
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
