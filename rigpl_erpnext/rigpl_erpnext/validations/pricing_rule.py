# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
    if not doc.priority:
        doc.priority = 1
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
