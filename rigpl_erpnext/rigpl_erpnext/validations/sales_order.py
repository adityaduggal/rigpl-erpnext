# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	letter_head= frappe.db.get_value("Sales Taxes and Charges Master", doc.taxes_and_charges ,"letter_head")
	if (doc.letter_head != letter_head):
		frappe.msgprint("Letter Head selected does not match with Sales Tax", raise_exception=1)

def on_submit(so,method):
	if so.track_trial == 1:
		no_of_team = 0
		
		for s_team in so.get("sales_team"):
			no_of_team = len(so.get("sales_team"))
		
		if no_of_team <> 1:
			frappe.msgprint("Please enter exactly one Sales Person who is responsible for carrying out the Trials", raise_exception=1)
		
		for sod in so.get("sales_order_details"):
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
			frappe.msgprint('{0}{1}'.format("Created New Trial Tracking: ", sod.name))
			tt.insert()
			
			
def on_cancel(so, method):
	if so.track_trial == 1:
		for sod in so.get("sales_order_details"):
			frappe.delete_doc("Trial Tracking", sod.name)