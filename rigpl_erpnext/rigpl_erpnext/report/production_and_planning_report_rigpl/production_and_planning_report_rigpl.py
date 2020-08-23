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
			"JC#:Link/Job Card:100", "Item:Link/Item:120", "Description::250", "Operation:Link/Operation:150",
			"Planned Qty:Float:80", "Priority:Int:80"
		]


def get_data(filters):
	if filters.get("summary") == 1:
		query = """SELECT jc.employee_name, jc.workstation, jc.production_item, jc.description, 
		jc.for_quantity, jc.total_completed_qty, jc.total_rejected_qty, jc.operation, jc.total_time_in_mins, 
		ROUND((jc.total_time_in_mins/ (jc.total_completed_qty + jc.total_rejected_qty)),2), jc.name
		FROM `tabProcess Job Card RIGPL` jc WHERE jc.docstatus = 1 ORDER BY jc.workstation, jc.production_item"""
	elif filters.get("production_planning") == 1:
		query = """SELECT jc.name, jc.production_item, jc.description, jc.operation, jc.for_quantity
		FROM `tabProcess Job Card RIGPL` jc WHERE jc.docstatus = 0 ORDER BY jc.operation, jc.production_item"""
	data = frappe.db.sql(query, as_list=1)
	return data


def get_conditions(filters):
	cond_jc = ""
	if filters.get("summary") == 1 and filters.get("production_planning") == 1:
		frappe.throw("Post Production and Planning cannot be checked together")
	if filters.get("summary") == 0 and filters.get("production_planning") == 0:
		frappe.throw("One of Post Production ot Planning needs to be Checked")
	if filters.get("from_date"):
		cond_jc += " AND jcop.to_time => '%s'" % filters.get("from_time")
	if filters.get("to_date"):
		cond_jc += " AND jcop.to_time <= '%s'" % filters.get("to_time")