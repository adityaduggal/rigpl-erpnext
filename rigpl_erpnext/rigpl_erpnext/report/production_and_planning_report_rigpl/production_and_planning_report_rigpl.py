# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	if filters.get("summary") == 1:
		return [
			"Employee Name::150", "Workstation:Link/Workstation:150",
			"Item Code:Link/Item:100", "Description::300", "Planned Qty:Float:100", "Completed Qty:Float:100",
			"Rejected Qty:Float:100", "Operation::200", "Total Time (mins):Float:80", "Time Per Pc:Float:80",
			"JC#:Link/Process Job Card RIGPL:100"
		]
	elif filters.get("production_planning") == 1:
		return [
			"JC#:Link/Process Job Card RIGPL:100", "Item:Link/Item:120", "Description::250",
			"Operation:Link/Operation:150", "Planned Qty:Float:80", "Priority:Int:80",
			"ROL:Int:80", "SO:Int:80", "PO:Int:80", "Plan:Int:80", "Prod:Float:80", "Total Actual:Float:80",
			"From Warehouse:Link/Warehouse:150", "To Warehouse:Link/Warehouse:150"
		]
	else:
		frappe.throw("Select one of the 2 checkboxes Post Production or Planning")


def get_data(filters):
	cond_jc = get_conditions(filters)
	if filters.get("summary") == 1:
		query = """SELECT jc.employee_name, jc.workstation, jc.production_item, jc.description, 
		jc.for_quantity, jc.total_completed_qty, jc.total_rejected_qty, jc.operation, jc.total_time_in_mins, 
		ROUND((jc.total_time_in_mins/ (jc.total_completed_qty + jc.total_rejected_qty)),2), jc.name
		FROM `tabProcess Job Card RIGPL` jc WHERE jc.docstatus = 1 %s 
		ORDER BY jc.workstation, jc.production_item""" % cond_jc
	elif filters.get("production_planning") == 1:
		query = """SELECT jc.name, jc.production_item, jc.description, jc.operation, jc.for_quantity, 
		IF(jc.priority=0, NULL, jc.priority),
		IF(ro.warehouse_reorder_level=0, NULL ,ro.warehouse_reorder_level) AS rol,
		IF(bn.on_so=0, NULL ,bn.on_so) AS on_so,
		IF(bn.on_po=0, NULL ,bn.on_so) AS on_po,
		IF(bn.plan=0, NULL ,bn.plan) AS plan,
		IF(bn.prod=0, NULL ,bn.prod) AS prod,
		IF(bn.act=0, NULL ,bn.act) AS act,
		IFNULL(jc.s_warehouse, "X") as s_wh,
		IFNULL(jc.t_warehouse, "X") as t_wh
		FROM `tabProcess Job Card RIGPL` jc 
		LEFT JOIN `tabItem Reorder` ro ON jc.production_item = ro.parent
		LEFT JOIN (SELECT item_code, SUM(reserved_qty) as on_so, SUM(ordered_qty) as on_po, SUM(actual_qty) as act,
			SUM(planned_qty) as plan, SUM(reserved_qty_for_production) as prod, SUM(indented_qty) as indent
			FROM `tabBin` GROUP BY item_code) bn 
			ON jc.production_item = bn.item_code
		WHERE jc.docstatus = 0 %s
		ORDER BY jc.operation, jc.production_item""" % cond_jc
	frappe.msgprint(query)
	data = frappe.db.sql(query, as_list=1)
	return data


def get_conditions(filters):
	cond_jc = ""
	cond_it = ""
	if filters.get("summary") == 1 and filters.get("production_planning") == 1:
		frappe.throw("Post Production and Planning cannot be checked together")
	if filters.get("summary") == 0 and filters.get("production_planning") == 0:
		frappe.throw("One of Post Production ot Planning needs to be Checked")
	if filters.get("from_date") and filters.get("summary") == 1:
		cond_jc += " AND jc.posting_date >= '%s'" % filters.get("from_date")
	if filters.get("to_date") and filters.get("summary") == 1:
		cond_jc += " AND jc.posting_date <= '%s'" % filters.get("to_date")
	if filters.get("summary") == 0:
		if filters.get("operation"):
			cond_jc += " AND jc.operation = '%s'" % filters.get("operation")
		if filters.get("bm"):
			cond_it += " AND bm.attribute_value = '%s'" % filters.get("bm")


	return cond_jc
