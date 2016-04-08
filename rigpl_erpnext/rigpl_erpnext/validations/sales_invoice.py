# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	c_form_tax =frappe.db.get_value("Sales Taxes and Charges Template", doc.taxes_and_charges ,"c_form_applicable")
	letter_head= frappe.db.get_value("Sales Taxes and Charges Template", doc.taxes_and_charges ,"letter_head")
	series = frappe.db.get_value("Sales Taxes and Charges Template", doc.taxes_and_charges ,"series")
	list_of_dns = []
	list_of_dn_details = []
	
	if (doc.c_form_applicable != c_form_tax):
		frappe.msgprint("C-Form applicable selection does not match with Sales Tax", raise_exception=1)
	if (doc.letter_head != letter_head):
		frappe.msgprint("Letter Head selected does not match with Sales Tax", raise_exception=1)
	if series not in doc.name:
		frappe.throw(("Series {0} selected for Tax {1} is not permitted").\
		format(doc.naming_series, doc.taxes_and_charges))
	elif doc.name[:3] == 'RBJ' and series == 'RB':
		frappe.throw(("Series {0} selected for Tax {1} is not permitted").\
		format(doc.naming_series, doc.taxes_and_charges))
	if doc.naming_series not in doc.name[:len(doc.naming_series)]:
		frappe.throw(("Series {0} selected for {1} is not permitted").\
		format(doc.naming_series, doc.name))
		
	for d in doc.items:
	
		#below code updates the CETSH number for the item in SI
		query = """SELECT a.attribute_value FROM `tabItem Variant Attribute` a 
			WHERE a.parent = '%s' AND a.attribute = 'CETSH Number' """ % d.item_code
		cetsh = frappe.db.sql(query, as_list=1)
		if cetsh:
			if d.cetsh_number:
				pass
			else:
				d.cetsh_number = cetsh[0][0]
		else:
			if d.cetsh_number:
				pass
			else:
				d.cetsh_number = '82079090'
		
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
				sod = dnd.so_detail
				query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod
				name = frappe.db.sql(query, as_list=1)
				if name:
					tt = frappe.get_doc("Trial Tracking", name[0][0])
					if tt:
						if tt.status is not ("Failed", "Passed") and tt.docstatus <> 1:
							frappe.msgprint("Cannot Make Invoice for Trial Items without Trial being Completed and Submitted", raise_exception=1)
	
	#Check the quantity of Invoice is EQUAL to the DN quantity and also check if the FULL DN is being invoices
	#Below code would check if the items are based on DN or NOT
	#If SI is NOT BASED on DN then it would ensure that the SI has the update stock button checked.
	
	for d in doc.items:
		if d.delivery_note is not None:
			dn = frappe.get_doc("Delivery Note", d.delivery_note)
			if dn is not None:
				for dnd in dn.items:
					if dnd.name == d.dn_detail:
						if d.qty > 0:
							if dnd.qty != d.qty:
								frappe.msgprint(("""Invoice Qty should be equal to DN Qty in line # {0}""").format(d.idx), raise_exception=1)
	if len(list_of_dns)==1 and list_of_dns[0] == None:
		if doc.update_stock != 1:
			for d in doc.items:
				if d.qty > 0:
					frappe.msgprint("Please check the Update Stock Button since Items are not based on DN", raise_exception=1)
	elif len(list_of_dns)>1:
		for i in range(len(list_of_dns)):
			if list_of_dns[i] is None:
				frappe.msgprint(("""Not allowed to enter items without DN make another invoice for such items check line # {0}""").format((d.idx)+1), raise_exception=1)
			else:
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
				sod = dnd.so_detail
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
				sod = dnd.so_detail
				query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod
				name = frappe.db.sql(query, as_list=1)
				if name:
					tt = frappe.get_doc("Trial Tracking", name[0][0])
					frappe.db.set(tt, 'invoice_no', None)
