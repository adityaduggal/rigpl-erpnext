from __future__ import unicode_literals
import frappe
from ....utils.job_card_utils import get_last_jc_for_so


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_so_entries(filters)

	return columns, data

def get_columns(filters):
	if filters.get("stock_status") == 1:
		return ["SO #:Link/Sales Order:100", "Date:Date:80", "Item Code:Link/Item:160",
				"Description::300", "Pending:Float:60", "Warehouse:Link/Warehouse:100", "Actual Qty:Float:60",
				"Reserved:Float:60", "Customer:Link/Customer:200"]
	elif filters.get("made_to_order") == 1:
		return [
			"SO#:Link/Sales Order:150", "Customer:Link/Customer:150", "SO Date:Date:80", "Item:Link/Item:120",
			"Description::450", "Pending:Float:60", "Ordered:Float:60", "JC#:Link/Process Job Card RIGPL:80",
			"PS#::150", "Status::60", "Operation:Link/Operation:100", "Priority:Int:50", "Planned Qty:Float:80",
			"Qty Avail:Float:80", "Remarks::400"
		]
	else:
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
	if filters.get("stock_status") == 1:
		query = """SELECT so.name, so.transaction_date, soi.item_code, soi.description, 
		(soi.qty - IFNULL(soi.delivered_qty, 0)), soi.warehouse, bn.actual_qty, bn.reserved_qty, so.customer
		FROM `tabSales Order` so, `tabSales Order Item` soi
		LEFT JOIN `tabBin` bn ON (bn.item_code=soi.item_code)
		LEFT JOIN `tabItem` it ON soi.item_code = it.name
		WHERE soi.`parent` = so.`name` AND bn.warehouse=soi.warehouse AND so.status != "Closed" AND so.docstatus = 1 
		AND so.transaction_date <= curdate() AND it.made_to_order != 1 AND bn.actual_qty >0 
		AND IFNULL(soi.delivered_qty,0) < IFNULL(soi.qty,0) %s ORDER BY so.transaction_date ASC""" % conditions
	elif filters.get("made_to_order") == 1:
		query = """SELECT so.name, so.customer, so.transaction_date, soi.item_code, soi.description, 
		(soi.qty - ifnull(soi.delivered_qty, 0)) as pend_qty, soi.qty, "" as jc_name, "NO JC" as jc_status, 
		"" as jc_operation, 0 as jc_priority, 0 as planned_qty, 0 as qty_avail, "Not in Production" as remarks, 
		soi.name as so_item
		FROM `tabSales Order` so, `tabSales Order Item` soi, `tabItem` it
		WHERE soi.parent = so.name AND so.docstatus = 1 AND (soi.qty - ifnull(soi.delivered_qty, 0)) > 0 
		AND so.status != "Closed" AND so.transaction_date <= curdate() AND soi.item_code = it.name 
		AND it.made_to_order = 1 %s ORDER BY so.transaction_date, so.name, soi.item_code, 
		soi.description""" % conditions
		so_data = frappe.db.sql(query, as_dict=1)
		so = update_so_data_with_job_card(so_data)
	else:
		query = """SELECT so.transaction_date, so.name, sod.delivery_date, so.customer, sod.item_code, sod.description, 
		(IFNULL(sod.qty,0) - IFNULL(sod.delivered_qty,0)), sod.qty, sod.delivered_qty, sod.base_rate, 
		((IFNULL(sod.qty,0) - IFNULL(sod.delivered_qty,0)) * sod.base_rate), so.po_no, sod.prd_notes, 
		if( so.transaction_date < date_sub(curdate(),interval 45 day),"DELAYED","OK"), 100-IFNULL(so.per_delivered,0), 
		((IFNULL(sod.qty,0) - IFNULL(sod.delivered_qty,0))/IFNULL(sod.qty,0)*100)
		FROM `tabSales Order` so, `tabSales Order Item` sod WHERE sod.parent = so.name AND so.docstatus = 1 
		AND so.status != "Closed" AND IFNULL(sod.delivered_qty,0) < IFNULL(sod.qty,0) %s 
		ORDER BY so.transaction_date DESC """ % conditions
	if filters.get("made_to_order") != 1:
		so = frappe.db.sql(query, as_list =1)
	if filters.get("made_to_order") != 1 and filters.get("stock_status") != 1:
		for i in range(len(so)):
			so[i][10] = so[i][6]*so[i][9]
	return so


def get_conditions(filters):
	conditions = ""
	if filters.get("stock_status") == 1 and filters.get("made_to_order") == 1:
		frappe.throw("Both Check boxes checked is Not Allowed")
	if filters.get("customer"):
		conditions += " and so.customer = '%s'" % filters["customer"]

	if filters.get("item"):
		conditions += " and sod.item_code = '%s'" % filters["item"]
	
	if filters.get("date"):
		conditions += " and so.transaction_date <= '%s'" % filters["date"]
	else:
		frappe.msgprint("Please select a Date first", raise_exception=1)

	return conditions


def update_so_data_with_job_card(so_dict):
	data = []
	for so in so_dict:
		line_data = []
		ps_dict = frappe.db.sql("""SELECT name FROM `tabProcess Sheet` 
			WHERE docstatus != 2 AND sales_order_item = '%s' ORDER BY creation""" % so.so_item, as_dict=1)
		so["ps_name"] = ""
		for ps in ps_dict:
			ps_link = """<a href="#Form/Process Sheet/%s" target="_blank">%s</a>""" % (ps.name, ps.name)
			so["ps_name"] += ps_link + "\n"
		so_jc = get_last_jc_for_so(so.so_item)
		if so_jc:
			so["jc_name"] = so_jc.name
			so["jc_status"] = so_jc.status
			so["jc_operation"] = so_jc.operation
			so["jc_priority"] = so_jc.priority
			so["planned_qty"] = so_jc.for_quantity
			so["qty_avail"] = so_jc.qty_available
			so["remarks"] = so_jc.remarks
		line_data = [so.name, so.customer, so.transaction_date, so.item_code, so.description, so.pend_qty, so.qty, so.jc_name,
					 so.ps_name, so.jc_status, so.jc_operation, so.jc_priority, so.planned_qty, so.qty_avail, so.remarks]
		data.append(line_data)
	return data
