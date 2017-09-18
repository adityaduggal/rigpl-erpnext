from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_so_entries(filters)

	return columns, data

def get_columns():


	return [
		"Date:Date:80", "SO #:Link/Sales Order:100", "ED Date:Date:80",
		"Customer:Link/Customer:180","Item Code:Link/Item:160",
		"Description::300", "Pending:Float:60", "Ordered:Float:60",
		"Delivered:Float:60", "Price:Currency:60", "Pending Amount:Currency:100",
		"PO#::80", "PRD Notes::100", "Status::100", "% SO Pending:Float:80",
		"% Item Pending:Float:80"
	]

def get_so_entries(filters):
	conditions = get_conditions(filters)
	
	query = """SELECT 
	 so.transaction_date, so.name, sod.delivery_date,
	 so.customer, sod.item_code, sod.description,
	 (ifnull(sod.qty,0)-ifnull(sod.delivered_qty,0)),
	 sod.qty, sod.delivered_qty, sod.base_rate,
	 ((ifnull(sod.qty,0)-ifnull(sod.delivered_qty,0)) * sod.base_rate) , 
	 so.po_no, sod.prd_notes, 
	 if( so.transaction_date < date_sub(curdate(),interval 45 day),"DELAYED","OK"),
	 100-ifnull(so.per_delivered,0), 
	 ((ifnull(sod.qty,0)-ifnull(sod.delivered_qty,0))/ifnull(sod.qty,0)*100)

	FROM
	 `tabSales Order` so, `tabSales Order Item` sod
	WHERE
	 sod.parent = so.name
	 AND so.docstatus = 1
	 AND so.status != "Closed"
	 AND ifnull(sod.delivered_qty,0) < ifnull(sod.qty,0) %s
	order by so.transaction_date desc """ % conditions
	
	so = frappe.db.sql(query, as_list =1)
	for i in range(len(so)):
		so[i][10] = so[i][6]*so[i][9]
	return so

def get_conditions(filters):
	conditions = ""
	if filters.get("customer"):
		conditions += " and so.customer = '%s'" % filters["customer"]

	if filters.get("item"):
		conditions += " and sod.item_code = '%s'" % filters["item"]
	
	if filters.get("date"):
		conditions += " and so.transaction_date <= '%s'" % filters["date"]
	else:
		frappe.msgprint("Please select a Date first", raise_exception=1)

	return conditions
