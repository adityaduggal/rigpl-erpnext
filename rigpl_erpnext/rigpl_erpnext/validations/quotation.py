# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from ...utils.sales_utils import check_get_pl_rate, get_hsn_code, check_taxes_integrity, check_dynamic_link, \
    validate_address_google_update


def validate(doc, method):
    if doc.customer_address:
        validate_address_google_update(doc.customer_address)
    if doc.shipping_address_name:
        validate_address_google_update(doc.shipping_address_name)
    if doc.quotation_to == 'Customer':
        check_dynamic_link(parenttype="Address", parent=doc.customer_address,
                           link_doctype="Customer", link_name=doc.party_name)
        check_dynamic_link(parenttype="Address", parent=doc.shipping_address_name,
                           link_doctype="Customer", link_name=doc.party_name)
        check_dynamic_link(parenttype="Contact", parent=doc.contact_person,
                           link_doctype="Customer", link_name=doc.party_name)
    else:
        if doc.customer_address:
            check_dynamic_link(parenttype="Address", parent=doc.customer_address,
                               link_doctype="Lead", link_name=doc.party_name)
        if doc.shipping_address_name:
            check_dynamic_link(parenttype="Address", parent=doc.shipping_address_name,
                               link_doctype="Lead", link_name=doc.party_name)

    check_taxes_integrity(doc)
    for rows in doc.items:
        if not rows.price_list:
            rows.price_list = doc.selling_price_list
        get_hsn_code(rows)
        check_get_pl_rate(doc, rows)
    # Check if Lead is Converted or Not, if the lead is converted
    # then don't allow it to be selected without linked customer
    if doc.quotation_to == "Lead":
        link = frappe.db.sql("""SELECT name FROM `tabCustomer` 
            WHERE lead_name = '%s'""" % (doc.party_name), as_list=1)
        if link:
            frappe.throw(("Lead {0} is Linked to Customer {1} so kindly make quotation for \
                Customer and not Lead").format(doc.party_name, link[0][0]))
    # below code updates the CETSH number for the item in Quotation and updates letter head
    letter_head_tax = frappe.db.get_value("Sales Taxes and Charges Template",
                                          doc.taxes_and_charges, "letter_head")
    doc.letter_head = letter_head_tax
