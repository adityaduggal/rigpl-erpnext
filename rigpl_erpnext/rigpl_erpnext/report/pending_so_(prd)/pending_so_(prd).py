# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	conditions_so = get_conditions(filters)
	columns = get_columns()
	data = get_items(filters, conditions_so)
	
	return columns, data
	
def get_columns():
	return[
	"SO Date:Date:80", "SO#:Link/Sales Order:100", "Item Code:Link/Item:120", 
	"Description::200", "Pending Qty:Float:90", "Ordered Qty:Float:90", "Draft PRD-Qty:Float:90",
	"Conf PRD Qty:Float:90", "PO-Qty:Float:90"
	]
	
def get_items(filters, conditions_so):
	data = []
	query = """SELECT 
		so.transaction_date, so.name, soi.item_code, soi.description,
		(soi.qty - ifnull(soi.delivered_qty, 0)), soi.qty, 
		(SELECT sum(prd.qty) FROM `tabProduction Order` prd WHERE prd.docstatus <> 2 AND
			prd.so_detail = soi.name AND prd.docstatus = 0),
		(SELECT sum(prd.qty) FROM `tabProduction Order` prd WHERE prd.docstatus <> 2 AND
			prd.so_detail = soi.name AND prd.docstatus = 1 AND prd.status <> "Stopped"),
		(SELECT sum(pod.qty) FROM `tabPurchase Order Item` pod, `tabPurchase Order` po WHERE po.docstatus = 1 AND
			po.name = pod.parent AND pod.so_detail = soi.name AND po.status <> "Stopped")
		FROM
		 `tabSales Order` so, `tabSales Order Item` soi
		
		WHERE
		 so.status <> "Closed" AND soi.parent = so.name
		 AND so.docstatus = 1 AND soi.qty > soi.delivered_qty 
		 AND so.transaction_date <= curdate() %s
		ORDER BY so.transaction_date DESC""" % (conditions_so)
		
	data = frappe.db.sql(query, as_list=1)
		
	
	return data
	
def get_conditions(filters):
	conditions_so = ""
	
	if filters.get("so_id"):
		conditions_so += " AND so.name = '%s'" % filters["so_id"]
		
	if filters.get("item"):
		conditions_so += " AND soi.item_code = '%s'" % filters["item"]
	
	return conditions_so