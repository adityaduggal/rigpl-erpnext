# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	for d in doc.items:
		#Check if the Item has a Stock Reconciliation after the date and time or NOT.
		#if there is a Stock Reconciliation then the Update would FAIL
		sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' 
			AND posting_date > '%s'""" %(d.item_code, d.s_warehouse, doc.posting_date), as_list=1)
		if sr:
			frappe.throw(("There is a Reconciliation for Item \
			Code: {0} after the posting date in warehouse {1}").format(d.item_code, d.s_warehouse))
		else:
			sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' 
			AND posting_date = '%s' AND posting_time >= '%s'""" \
			%(d.item_code, d.s_warehouse, doc.posting_date, doc.posting_time), as_list=1)
			if sr:
				frappe.throw(("There is a Reconciliation for Item \
				Code: {0} after the posting time in warehouse {1}").format(d.item_code, d.s_warehouse))
			else:
				pass
		#Check the Stock Reconciliation for Target Warehouse as well
		sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' 
			AND posting_date > '%s'""" %(d.item_code, d.t_warehouse, doc.posting_date), as_list=1)
		if sr:
			frappe.throw(("There is a Reconciliation for Item \
			Code: {0} after the posting date in warehouse {1}").format(d.item_code, d.t_warehouse))
		else:
			sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' 
			AND posting_date = '%s' AND posting_time >= '%s'""" \
			%(d.item_code, d.t_warehouse, doc.posting_date, doc.posting_time), as_list=1)
			if sr:
				frappe.throw(("There is a Reconciliation for Item \
				Code: {0} after the posting time in warehouse {1}").format(d.item_code, d.t_warehouse))
			else:
				pass
		
		
		#Get Stock Valuation from Valuation Rate Table
		query = """SELECT vr.name FROM `tabValuation Rate` vr where vr.disabled = 'No' and vr.item_code = '%s' """ % d.item_code
		vr_name = frappe.db.sql(query, as_list=1)
		if vr_name <> []:
			vr = frappe.get_doc("Valuation Rate", vr_name[0][0])
			if d.item_code == vr.item_code:
				d.basic_rate = vr.valuation_rate
				d.valuation_rate = vr.valuation_rate