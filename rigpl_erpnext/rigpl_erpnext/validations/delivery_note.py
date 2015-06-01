# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def on_submit(doc, method):
	for dnd in doc.get("items"):
		so = frappe.get_doc("Sales Order", dnd.against_sales_order)
		sod = frappe.get_doc("Sales Order Item", dnd.so_detail)
		if so.track_trial == 1:
			query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
			name = frappe.db.sql(query, as_list=1)
			tt = frappe.get_doc("Trial Tracking", name[0][0])
			if tt:
				frappe.db.set(tt, 'status', 'Material Ready')
				frappe.msgprint('{0}{1}'.format("Updated Status of Trial No: ", name[0][0]))
				
def on_cancel(doc, method):
	for dnd in doc.get("items"):
		so = frappe.get_doc("Sales Order", dnd.against_sales_order)
		sod = frappe.get_doc("Sales Order Item", dnd.so_detail)
		if so.track_trial == 1:
			query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
			name = frappe.db.sql(query, as_list=1)
			tt = frappe.get_doc("Trial Tracking", name[0][0])
			if tt:
				frappe.db.set(tt, 'status', 'In Production')
				frappe.msgprint('{0}{1}'.format("Updated Status of Trial No: ", name[0][0]))