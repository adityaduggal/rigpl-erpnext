# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_entries(filters)

	return columns, data

def get_columns(filters):
	return [
		"ID:Link/Leave Application:100", "From Date:Date:80", "To Date:Date:80", 
		"Employee:Link/Employee:150", "Employee Name::200", "Leave Type::130", 
		"Total Leaves:Int:60", "Leave Balance Before:Int:60", "Posting Date:Date:100",
		"Created By::150", "Created On::200"
		]

def get_entries(filters):
	la = frappe.qb.DocType("Leave Application")
	emp = frappe.qb.DocType("Employee")
	query = (
		frappe.qb.from_(la)
		.join(emp).on(emp.name == la.employee)
		.select(la.name, la.from_date, la.to_date, la.employee, emp.employee_name, la.leave_type,
			la.total_leave_days, la.leave_balance, la.posting_date, la.owner, la.creation)
		.where(la.docstatus != 2)
		.orderby(la.from_date)
		.orderby(la.to_date)
		.orderby(emp.date_of_joining)
		.orderby(la.name)
	)
	for key, field in (("branch", "branch"), ("department", "department"), ("employee", "name")):
		if filters.get(key):
			query = query.where(emp[field] == filters[key])
	if filters.get("from_date"):
		query = query.where((la.from_date >= filters["from_date"]) | (la.to_date >= filters["from_date"]))
	if filters.get("to_date"):
		query = query.where((la.to_date <= filters["to_date"]) | (la.from_date <= filters["to_date"]))
	if filters.get("status"):
		query = query.where(la.status == filters["status"])
		if filters["status"] == "Approved":
			query = query.where(la.docstatus == 1)
	return query.run(as_list=1)
