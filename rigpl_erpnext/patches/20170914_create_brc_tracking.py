# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe, erpnext
from rigpl_erpnext.rigpl_erpnext.validations.sales_invoice import new_brc_tracking

def execute():
	si_list = frappe.db.sql("""SELECT si.name, si.posting_date, si.customer
		FROM `tabSales Invoice` si, `tabAddress` ad, `tabSales Taxes and Charges Template` stct
		WHERE si.docstatus = 1 AND si.shipping_address_name = ad.name AND ad.country != 'India'
			AND si.taxes_and_charges = stct.name AND stct.is_export = 1
		ORDER BY si.posting_date ASC""", as_list =1)
	if si_list:
		for si in si_list:
			si_doc = frappe.get_doc("Sales Invoice", si[0])
			new_brc_tracking(si_doc, frappe)
			print ("Created New BRC for Invoice # " + si[0] + " of Customer: " + si[2] + " dated: " + str(si[1]))

def update_grand_total():
	brc_list = frappe.db.sql("""SELECT name FROM `tabBRC MEIS Tracking`""", as_list=1)
	for brc in brc_list:
		brc_doc = frappe.get_doc('BRC MEIS Tracking', brc[0])
		brc_doc.save()
		print("BRC # " + brc[0] + " Updated")