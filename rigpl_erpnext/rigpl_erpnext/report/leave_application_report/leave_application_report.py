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
	conditions = get_conditions(filters)
	
	query = """SELECT la.name, la.from_date, la.to_date, la.employee,
		emp.employee_name, la.leave_type, la.total_leave_days, 
		la.leave_balance, la.posting_date, la.owner, la.creation
		FROM `tabLeave Application` la, `tabEmployee` emp
		WHERE la.docstatus <> 2 AND
			la.employee = emp.name %s
		ORDER BY la.from_date, la.to_date, emp.date_of_joining""" %conditions
	data = frappe.db.sql(query, as_list=1)
	
	return data

def get_conditions(filters):
	conditions = ""

	if filters.get("branch"):
		conditions += " AND emp.branch = '%s'" % filters["branch"]

	if filters.get("department"):
		conditions += " AND emp.department = '%s'" % filters["department"]
				
	if filters.get("employee"):
		conditions += " AND emp.name = '%s'" % filters["employee"]
		
	if filters.get("from_date"):
		conditions += " AND (la.from_date >='%s' OR la.to_date >= '%s')" % (filters["from_date"], filters["from_date"])

	if filters.get("to_date"):
		conditions += " AND (la.to_date <='%s' OR la.from_date <='%s')" % (filters["to_date"], filters["to_date"])
		
	if filters.get("status"):
		if filters.get("status") == "Approved":
			conditions += " AND la.status ='%s' AND la.docstatus = 1" % filters["status"]
		else:
			conditions += " AND la.status ='%s'" % filters["status"]
		
	return conditions