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
	if filters.get("without_roster")<>1:
		return [
			"ID:Link/Roster:80", "From Date:Date:80", "To Date:Date:80", 
			"Shift:Link/Shift Details:100", "Shift Name::150",
			"Employee ID:Link/Employee:100", "Employee Name::200", "Branch::80", "Department::80",
			"Designation::100", "Shift In:Time:100", "Shift Out:Time:100", "Hours Required::80"
			]
	else:
		return [
			"Employee ID:Link/Employee:100", "Employee Name::200", "Branch::80", "Department::80",
			"Designation::100", "Joining Date:Date:80", "Relieving Date:Date:80"
			]

def get_entries(filters):
	conditions_emp = get_conditions(filters)[0]
	conditions_ro = get_conditions(filters)[1]
	conditions_sh = get_conditions(filters)[2]
	
	if filters.get("without_roster") <> 1:
		query = """SELECT ro.name, ro.from_date, ro.to_date, ro.shift, sh.title,
			emp.name, emp.employee_name, ifnull(emp.branch,"-"), ifnull(emp.department,"-"),
			ifnull(emp.designation,"-"), sh.in_time, sh.out_time, sh.hours_required_per_day
			FROM `tabRoster` ro, `tabRoster Details` rod, `tabShift Details` sh, `tabEmployee` emp
			WHERE
				rod.parent = ro.name AND
				sh.name = ro.shift AND
				emp.name = rod.employee %s %s %s
			ORDER BY ro.from_date, ro.to_date,emp.date_of_joining""" %(conditions_emp,conditions_ro, conditions_sh)
	else:
		query = """SELECT emp.name, emp.employee_name, ifnull(emp.branch,"-"), 
			ifnull(emp.department,"-"), ifnull(emp.designation,"-"), emp.date_of_joining,
			IFNULL(emp.relieving_date, '2099-12-31')
			FROM `tabEmployee` emp
			WHERE
				emp.name NOT IN (
				SELECT emp.name
				FROM `tabRoster` ro, `tabRoster Details` rod, `tabEmployee` emp
				WHERE rod.parent = ro.name AND rod.employee = emp.name %s
				) AND emp.date_of_joining < '%s' AND
				IFNULL(emp.relieving_date,'2099-12-31') > '%s' %s
			ORDER BY emp.date_of_joining""" %(conditions_ro, filters.get("to_date"), filters.get("from_date"),conditions_emp)

	data = frappe.db.sql(query, as_list=1)
	
	return data

def get_conditions(filters):
	conditions_emp = ""
	conditions_ro = ""
	conditions_sh = ""
	
	if filters.get("branch"):
		conditions_emp += " AND emp.branch = '%s'" % filters["branch"]

	if filters.get("department"):
		conditions_emp += " AND emp.department = '%s'" % filters["department"]
		
	if filters.get("designation"):
		conditions_emp += " AND emp.designation = '%s'" % filters["designation"]
		
	if filters.get("employee"):
		conditions_emp += " AND emp.name = '%s'" % filters["employee"]
		
	if filters.get("from_date") and filters.get("to_date"):
		if filters["from_date"] > filters["to_date"]:
			frappe.throw("From Date cannot be after To Date")
		else:
			conditions_ro += " AND ((ro.from_date <='%s' AND ro.to_date <= '%s' AND \
				ro.to_date >= '%s') OR (ro.from_date <= '%s' AND ro.to_date >= '%s'))" % \
				(filters["from_date"], filters["to_date"], filters["from_date"], \
				filters["to_date"], filters["from_date"])

		
	if filters.get("shift") and filters.get("without_roster") <> 1:
		conditions_sh += " AND ro.shift ='%s'" % filters["shift"]

		
	return conditions_emp, conditions_ro, conditions_sh