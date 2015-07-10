# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	c_form_tax =frappe.db.get_value("Sales Taxes and Charges Template", doc.taxes_and_charges ,"c_form_applicable")
	letter_head= frappe.db.get_value("Sales Taxes and Charges Template", doc.taxes_and_charges ,"letter_head")
	list_of_dns = []
	list_of_dn_details = []
	
	if (doc.c_form_applicable != c_form_tax):
		frappe.msgprint("C-Form applicable selection does not match with Sales Tax", raise_exception=1)
	if (doc.letter_head != letter_head):
		frappe.msgprint("Letter Head selected does not match with Sales Tax", raise_exception=1)
		
	for d in doc.items:
		if d.delivery_note not in list_of_dns:
			list_of_dns.extend([d.delivery_note])
		
		if d.dn_detail not in list_of_dn_details:
			list_of_dn_details.extend([d.dn_detail])
			
		if d.sales_order is not None:
			if d.delivery_note is None:
				frappe.msgprint(("""Error in Row# {0} has SO# {1} but there is no DN.
				Hence making of Invoice is DENIED""").format(d.idx, d.sales_order), raise_exception=1)
		elif d.delivery_note is not None:
			if d.sales_order is None:
				frappe.msgprint(("""Error in Row# {0} has DN# {1} but there is no SO.
				Hence making of Invoice is DENIED""").format(d.idx, d.delivery_note), raise_exception=1)
		if d.sales_order is not None:
			so = frappe.get_doc("Sales Order", d.sales_order)
			if so.track_trial == 1:
				dnd = frappe.get_doc("Delivery Note Item", d.dn_detail)
				sod = dnd.prevdoc_detail_docname
				query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod
				name = frappe.db.sql(query, as_list=1)
				if name:
					tt = frappe.get_doc("Trial Tracking", name[0][0])
					if tt:
						if tt.status is not ("Failed", "Passed") and tt.docstatus <> 1:
							frappe.msgprint("Cannot Make Invoice for Trial Items without Trial being Completed and Submitted", raise_exception=1)
	
	#Check the quantity of Invoice is EQUAL to the DN quantity and also check if the FULL DN is being invoices

	for d in doc.items:
		dn = frappe.get_doc("Delivery Note", d.delivery_note)
		if d.delivery_note is not None:
			for dnd in dn.items:
				if dnd.name == d.dn_detail:
					if dnd.qty != d.qty:
						frappe.msgprint(("""Invoice Qty should be equal to DN Qty in line # {0}""").format(d.idx), raise_exception=1)
	
	for i in range(len(list_of_dns)):
		dn = frappe.get_doc("Delivery Note", list_of_dns[i])
		for d in dn.items:
			if d.name not in list_of_dn_details:
				frappe.msgprint(("""Item Code {0} in DN# {1} is not mentioned in the Invoice""").format(d.item_code, dn.name), raise_exception=1)

def on_submit(doc,method):
	user = frappe.session.user
	query = """SELECT role from `tabUserRole` where parent = '%s' """ %user
	roles = frappe.db.sql(query, as_list=1)
	
	for d in doc.items:
		if d.sales_order is None:
			if d.delivery_note is None:
				if doc.ignore_pricing_rule == 1:
					if any("System Manager" in s  for s in roles):
						pass
					else:
						frappe.msgprint("You are not Authorised to Submit this Transaction ask a System Manager", raise_exception=1)
		if d.sales_order is not None:
			so = frappe.get_doc("Sales Order", d.sales_order)
			if so.track_trial == 1:
				dnd = frappe.get_doc("Delivery Note Item", d.dn_detail)
				sod = dnd.prevdoc_detail_docname
				query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod
				name = frappe.db.sql(query, as_list=1)
				if name:
					tt = frappe.get_doc("Trial Tracking", name[0][0])
					frappe.db.set(tt, 'invoice_no', doc.name)

def on_cancel(doc,method):
	for d in doc.items:
		if d.sales_order is not None:
			so = frappe.get_doc("Sales Order", d.sales_order)
			if so.track_trial == 1:
				dnd = frappe.get_doc("Delivery Note Item", d.dn_detail)
				sod = dnd.prevdoc_detail_docname
				query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod
				name = frappe.db.sql(query, as_list=1)
				if name:
					tt = frappe.get_doc("Trial Tracking", name[0][0])
					frappe.db.set(tt, 'invoice_no', None)
