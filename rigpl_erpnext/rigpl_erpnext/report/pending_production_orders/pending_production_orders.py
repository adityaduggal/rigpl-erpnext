# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	conditions_prd = get_conditions(filters)
	columns = get_columns()
	data = get_items(filters, conditions_prd)
	
	return columns, data
	
def get_columns():
	return[
	"PRD No:Link/Production Order:120", "WH::90", 
	"PRD Date:Date:80", "Priority:Int:20", "Item Code:Link/Item:120", 
	"Item Description::280", "PPRD:Float:50", "Qty:Float:50", "PRD:Float:50",
	"RM to Use::300", "Remarks::200", "SO#:Link/Sales Order:150",
	"Owner::100", "Modified By::100"
	]
	
def get_items(filters, conditions_prd):
	data = []
	query = """SELECT
		prd.name, prd.fg_warehouse, prd.production_order_date, prd.priority, 
		prd.production_item, prd.item_description, 
		(IFNULL(prd.qty,0)- IFNULL(prd.produced_qty,0)), prd.qty,
		prd.produced_qty, prd.rm_description, prd.remarks, prd.sales_order, 
		prd.owner, prd.modified_by
		
		FROM
			`tabProduction Order` prd
		LEFT JOIN `tabItem Variant Attribute` bm ON prd.production_item = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` tt ON prd.production_item = tt.parent
			AND tt.attribute = 'Tool Type'
		WHERE
			prd.production_order_date <= CURDATE()+1 AND
			(IFNULL(prd.qty,0)- IFNULL(prd.produced_qty,0)) > 0 %s
		
		ORDER BY
			prd.production_order_date, prd.priority""" % (conditions_prd)
	data = frappe.db.sql(query, as_list=1)
		
	
	return data
	
def get_conditions(filters):
	conditions_prd = ""
	
	if filters.get("so_id"):
		conditions_prd += " AND prd.sales_order = '%s'" % filters["so_id"]
		
	if filters.get("item"):
		conditions_prd += " AND prd.production_item = '%s'" % filters["item"]
		
	if filters.get("from_date"):
		conditions_prd += " AND prd.production_order_date >= '%s'" % filters["from_date"]
		
	if filters.get("to_date"):
		conditions_prd += " AND prd.production_order_date <= '%s'" % filters["to_date"]
	
	if filters.get("bm"):
		conditions_prd += " AND bm.attribute_value = '%s'" % filters["bm"]
		
	if filters.get("tt"):
		conditions_prd += " AND tt.attribute_value = '%s'" % filters["tt"]
		
	if filters.get("status") == "Submitted":
		conditions_prd += "AND prd.docstatus = 1 AND prd.status <> 'Stopped'"
	else:
		conditions_prd += "AND prd.docstatus = 0"
	
	return conditions_prd