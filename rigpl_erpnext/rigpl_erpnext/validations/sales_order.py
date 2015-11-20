# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	for sod in doc.get("items"):
		#below code updates the CETSH number for the item in SO
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

def on_submit(so,method):
	if so.track_trial == 1:
		no_of_team = 0
		
		for s_team in so.get("sales_team"):
			no_of_team = len(so.get("sales_team"))
		
		if no_of_team <> 1:
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