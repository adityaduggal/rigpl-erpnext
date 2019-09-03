# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import nowdate
from rigpl_erpnext.utils.sales_utils import *

def validate(doc,method):
	check_dynamic_link(parenttype="Address", parent=doc.customer_address, \
		link_doctype="Customer", link_name=doc.customer)
	check_dynamic_link(parenttype="Address", parent=doc.shipping_address_name, \
		link_doctype="Customer", link_name=doc.customer)
	check_dynamic_link(parenttype="Contact", parent=doc.contact_person, \
		link_doctype="Customer", link_name=doc.customer)
	update_fields(doc,method)
	check_gst_rules(doc.customer_address, doc.shipping_address_name, \
		doc.taxes_and_charges, doc.naming_series, doc.name, series=2)
	check_taxes_integrity(doc)
	frappe.msgprint("Selected Addresses Both Billing and Shipping Cannot be Changed Later")
	check_price_list(doc,method)
	cust_doc = frappe.get_doc("Customer", doc.customer)
	if cust_doc.customer_primary_contact is None:
		frappe.throw("Cannot Book Sales Order since Customer " + cust_doc.name + \
			" does not have a Primary Contact Defined")

	if cust_doc.customer_primary_address is None:
		frappe.throw("Cannot Book Sales Order since Customer " + cust_doc.name + \
			" does not have a Primary Address Defined")

	if cust_doc.sales_team is None:
		frappe.throw("Cannot Book Sales Order since Customer " + cust_doc.name + \
			" does not have a Sales Team Defined")

def check_price_list(doc,method):
	for it in doc.items:
		if it.price_list:
			check_get_pl_rate(doc, it)
		else:
			it.price_list = doc.selling_price_list
			check_get_pl_rate(doc, it)

def update_fields(doc,method):
	doc.shipping_address_title = frappe.get_value("Address", \
		doc.shipping_address_name, "address_title")
	doc.transaction_date = nowdate()
	if doc.delivery_date < nowdate():
		doc.delivery_date = nowdate()
	for d in doc.items:
		if d.delivery_date < nowdate():
			d.delivery_date = nowdate()

	letter_head_tax = frappe.db.get_value("Sales Taxes and Charges Template", \
		doc.taxes_and_charges, "letter_head")
	doc.letter_head = letter_head_tax
	
	for items in doc.items:
		get_hsn_code(items)

def on_submit(so,method):
	so.submitted_by = so.modified_by
	if so.track_trial == 1:
		no_of_team = 0
		
		for s_team in so.get("sales_team"):
			no_of_team = len(so.get("sales_team"))
		
		if no_of_team != 1:
			frappe.msgprint("Please enter exactly one Sales Person who is responsible for carrying out the Trials", raise_exception=1)
		
		for sod in so.get("items"):
			tt=frappe.new_doc("Trial Tracking")
			tt.prevdoc_detail_docname = sod.name
			tt.against_sales_order = so.name
			tt.customer = so.customer
			tt.item_code = sod.item_code
			tt.qty = sod.qty
			tt.description = sod.description
			tt.base_rate = sod.base_rate
			tt.trial_owner = s_team.sales_person
			tt.status = "In Production"
			tt.insert()
			query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
			name = frappe.db.sql(query, as_list=1)
			frappe.msgprint('{0}{1}'.format("Created New Trial Tracking Number: ", name[0][0]))
			
			
def on_cancel(so, method):
	if so.track_trial == 1:
		for sod in so.get("items"):
			query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
			name = frappe.db.sql(query, as_list=1)
			if name:
				frappe.delete_doc("Trial Tracking", name[0])
				frappe.msgprint('{0}{1}'.format("Deleted Trial Tracking No: ", name[0][0]))
