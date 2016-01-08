# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	#Check if the Item has a Stock Reconciliation after the date and time or NOT.
	#if there is a Stock Reconciliation then the Update would FAIL
	for dnd in doc.get("items"):
		sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' AND voucher_type = 'Stock Reconciliation'
			AND posting_date > '%s'""" %(dnd.item_code, dnd.warehouse, doc.posting_date), as_list=1)
		if sr:
			frappe.throw(("There is a Reconciliation for Item \
			Code: {0} after the posting date").format(dnd.item_code))
		else:
			sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' AND voucher_type = 'Stock Reconciliation'
			AND posting_date = '%s' AND posting_time >= '%s'""" \
			%(dnd.item_code, dnd.warehouse, doc.posting_date, doc.posting_time), as_list=1)
			if sr:
				frappe.throw(("There is a Reconciliation for Item \
				Code: {0} after the posting time").format(dnd.item_code))
			else:
				pass
	
	

def on_submit(doc, method):
	for dnd in doc.get("items"):
		if dnd.so_detail and dnd.against_sales_order:
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
		#Code to update the status in Trial Tracking
		if dnd.so_detail and dnd.against_sales_order:
			so = frappe.get_doc("Sales Order", dnd.against_sales_order)
			sod = frappe.get_doc("Sales Order Item", dnd.so_detail)
			if so.track_trial == 1:
				query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
				name = frappe.db.sql(query, as_list=1)
				tt = frappe.get_doc("Trial Tracking", name[0][0])
				if tt:
					frappe.db.set(tt, 'status', 'In Production')
					frappe.msgprint('{0}{1}'.format("Updated Status of Trial No: ", name[0][0]))