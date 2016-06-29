# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
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
	#below code updates the CETSH number for the item in Quotation
	for sod in doc.get("items"):
		query = """SELECT a.attribute_value FROM `tabItem Variant Attribute` a 
			WHERE a.parent = '%s' AND a.attribute = 'CETSH Number' """ % sod.item_code
		cetsh = frappe.db.sql(query, as_list=1)
		if cetsh:
			if sod.cetsh_number:
				pass
			else:
				sod.cetsh_number = cetsh[0][0]
		else:
			if sod.cetsh_number:
				pass
			else:
				sod.cetsh_number = '82079090'
		
	letter_head= frappe.db.get_value("Sales Taxes and Charges Template", doc.taxes_and_charges ,"letter_head")
	if (doc.letter_head != letter_head):
		frappe.msgprint("Letter Head selected does not match with Sales Tax", raise_exception=1)