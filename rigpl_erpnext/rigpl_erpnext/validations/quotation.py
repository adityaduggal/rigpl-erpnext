# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from rigpl_erpnext.utils.sales_utils import \
	check_get_pl_rate, get_hsn_code, check_taxes_integrity, check_dynamic_link

def validate(doc,method):
	if doc.quotation_to == 'Customer':
		check_dynamic_link(parenttype="Address", parent=doc.customer_address, \
			link_doctype="Customer", link_name=doc.customer)
		check_dynamic_link(parenttype="Address", parent=doc.shipping_address_name, \
			link_doctype="Customer", link_name=doc.customer)
		check_dynamic_link(parenttype="Contact", parent=doc.contact_person, \
			link_doctype="Customer", link_name=doc.customer)
	else:
		if doc.customer_address:
			check_dynamic_link(parenttype="Address", parent=doc.customer_address, \
				link_doctype="Lead", link_name=doc.lead)
		if doc.shipping_address_name:
			check_dynamic_link(parenttype="Address", parent=doc.shipping_address_name, \
				link_doctype="Lead", link_name=doc.lead)

	check_taxes_integrity(doc)
	for rows in doc.items:
		if not rows.price_list:
			rows.price_list = doc.selling_price_list
		get_hsn_code(rows)
		check_get_pl_rate(doc, rows)
	#Check if Lead is Converted or Not, if the lead is converted 
	#then don't allow it to be selected without linked customer
	if doc.lead:
		link = frappe.db.sql("""SELECT name FROM `tabCustomer` 
			WHERE lead_name = '%s'"""%(doc.lead), as_list=1)
		if doc.customer is None and link:
			frappe.throw(("Lead {0} is Linked to Customer {1} so kindly make quotation for \
				Customer and not Lead").format(doc.lead, link[0][0]))
		elif doc.customer:
			if doc.customer != link[0][0]:
				frappe.throw(("Customer {0} is not linked to Lead {1} hence cannot be set\
				in the Quotation").format(doc.customer, doc.lead))
	#below code updates the CETSH number for the item in Quotation and updates letter head
	letter_head_tax = frappe.db.get_value("Sales Taxes and Charges Template", \
		doc.taxes_and_charges, "letter_head")
	doc.letter_head = letter_head_tax