# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	conditions = get_conditions(filters)
	columns = get_columns(filters)
	data = get_items(filters, conditions)
	
	return columns, data
	
def get_columns(filters):
	if filters.get("subcontracting") == 1:
		return[
		"PO# :Link/Purchase Order:120", "PO Date:Date:80", 
		"SCH Date:Date:80", "Supplier:Link/Supplier:200", "Item Code:Link/Item:120", 
		"Description::280", "Pend Qty:Float:60", "Ordered Qty:Float:60", "Rejected Qty:Float:60",
		"UoM::50", "Price:Currency:80", "Sub Contract Item Code:Link/Item:120", 
		"Item Qty:Float:100", "Stock Entry:Link/Stock Entry:150"
		]
	else:
		return[
		"PO# :Link/Purchase Order:120", "PO Date:Date:80", 
		"SCH Date:Date:80", "Supplier:Link/Supplier:200", "Item Code:Link/Item:120", 
		"Description::280", "Pend Qty:Float:60", "Ordered Qty:Float:60", "Rejected Qty:Float:60",
		"UoM::50", "Price:Currency:80"
		]
		
def get_items(filters, conditions):
	if filters.get("subcontracting") == 1:
		query = """SELECT po.name, po.transaction_date, pod.schedule_date, po.supplier, 
			pod.item_code, pod.description, (pod.qty - pod.received_qty), 
			pod.qty, pod.returned_qty, pod.stock_uom, pod.base_rate, pod.subcontracted_item,
			pod.conversion_factor, ste.name
			FROM `tabPurchase Order` po, `tabPurchase Order Item` pod, `tabStock Entry` ste
			WHERE po.docstatus = 1 AND po.name = pod.parent AND ste.purchase_order = po.name
				AND po.status <> 'Closed' AND IFNULL(pod.received_qty,0) < IFNULL(pod.qty,0)
				%s
			ORDER BY po.transaction_date, pod.schedule_date""" %conditions
	else:
		query = """SELECT po.name, po.transaction_date, pod.schedule_date, po.supplier, 
			pod.item_code, pod.description, (pod.qty - pod.received_qty), 
			pod.qty, pod.returned_qty, pod.stock_uom, pod.base_rate
			FROM `tabPurchase Order` po, `tabPurchase Order Item` pod
			WHERE po.docstatus = 1 AND po.name = pod.parent 
				AND po.status <> 'Closed' AND IFNULL(pod.received_qty,0) < IFNULL(pod.qty,0) %s
			ORDER BY po.transaction_date, pod.schedule_date""" %conditions
		
	data = frappe.db.sql(query, as_list=1)
	return data
	
def get_conditions(filters):
	conditions = ""
	
	if filters.get("subcontracting") == 1:
		conditions += " AND po.is_subcontracting = 1"
	else:
		conditions += " AND po.is_subcontracting = 0"
	
	if filters.get("item"):
		conditions += " AND pod.item_code = '%s'" % filters["item"]
		
	if filters.get("supplier"):
		conditions += " AND po.supplier = '%s'" % filters["supplier"]
		
	if filters.get("date"):
		conditions += " AND po.transaction_date <= '%s'" % filters["date"]
	return conditions