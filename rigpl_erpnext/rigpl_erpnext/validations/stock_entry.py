# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	#If STE linked to PO then status of Stock Entry cannot be different from PO 
	#along with posting date and time
	if doc.purchase_order:
		po = frappe.get_doc("Purchase Order", doc.purchase_order)
		doc.posting_date = po.transaction_date
		doc.posting_time = '23:59:59'
	elif doc.purchase_receipt_no:
		grn = frappe.get_doc("Purchase Receipt", doc.purchase_receipt_no)
		doc.posting_date = grn.posting_date
		doc.posting_time = grn.posting_time
	else:
		for d in doc.items:
			#STE for Subcontracting WH only possible for linked with PO STE
			if d.t_warehouse:
				wht = frappe.get_doc("Warehouse", d.t_warehouse)
				if wht.is_subcontracting_warehouse == 1:
					frappe.throw("Subcontracting Warehouse Stock Entries only possible with PO or GRN")
			if d.s_warehouse:
				whs = frappe.get_doc("Warehouse", d.s_warehouse)
				if whs.is_subcontracting_warehouse == 1:
					frappe.throw("Subcontracting Warehouse Stock Entries only possible with PO or GRN")
	
	#Check if the Item has a Stock Reconciliation after the date and time or NOT.
	#if there is a Stock Reconciliation then the Update would FAIL
	for d in doc.items:
		sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' AND voucher_type = 'Stock Reconciliation'
			AND posting_date > '%s'""" %(d.item_code, d.s_warehouse, doc.posting_date), as_list=1)
		if sr:
			frappe.throw(("There is a Reconciliation for Item \
			Code: {0} after the posting date in source warehouse {1}").format(d.item_code, d.s_warehouse))
		else:
			sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' AND voucher_type = 'Stock Reconciliation'
			AND posting_date = '%s' AND posting_time >= '%s'""" \
			%(d.item_code, d.s_warehouse, doc.posting_date, doc.posting_time), as_list=1)
			
			if sr:
				frappe.throw(("There is a Reconciliation for Item \
				Code: {0} after the posting time in source warehouse {1}").format(d.item_code, d.s_warehouse))
			else:
				pass
		#Check the Stock Reconciliation for Target Warehouse as well
		sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' AND voucher_type = 'Stock Reconciliation'
			AND posting_date > '%s'""" %(d.item_code, d.t_warehouse, doc.posting_date), as_list=1)
		if sr:
			frappe.throw(("There is a Reconciliation for Item \
			Code: {0} after the posting date in target warehouse {1}").format(d.item_code, d.t_warehouse))
		else:
			sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` 
			WHERE item_code = '%s' AND warehouse = '%s' AND voucher_type = 'Stock Reconciliation'
			AND posting_date = '%s' AND posting_time >= '%s'""" \
			%(d.item_code, d.t_warehouse, doc.posting_date, doc.posting_time), as_list=1)
			if sr:
				frappe.msgprint(sr)
				frappe.throw(("There is a Reconciliation for Item \
				Code: {0} after the posting time in target warehouse {1}").format(d.item_code, d.t_warehouse))
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