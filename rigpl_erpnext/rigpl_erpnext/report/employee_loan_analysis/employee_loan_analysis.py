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
	if filters.get("detail"):
		return [
			"Employee::100", "Employee Name::150", "Loan Date::80", 
			"Loan #::80", "Loan Amount::80", "Total Due::80"
			]
	else:
		return [
			"Employee::100", "Employee Name::150", "Opening Balance::80", 
			"Loan Given::80", "Loan Deducted::80", "Closing Balance::80"
			]

def get_entries(filters):
	conditions_emp = get_conditions(filters)[0]
	conditions_el = get_conditions(filters)[1]
	loan_map = get_loan_given(filters)
	from_date = filters.get("from_date")
	query = """SELECT emp.name, emp.employee_name
		FROM 
			`tabEmployee` emp
		WHERE
			IFNULL(emp.relieving_date, '2099-12-31') >= '%s' %s
		ORDER BY emp.name
		""" %(from_date, conditions_emp)
	#frappe.msgprint(query)
	data = frappe.db.sql(query, as_dict=1)
	
	#frappe.msgprint(data)
	
	return data

def get_loan_given(filters):
	conditions_el = get_conditions(filters)[1]
	frappe.msgprint("Hello")
	loan_list = frappe.db.sql("""SELECT el.name, el.posting_date, eld.employee, eld.loan_amount
		FROM `tabEmployee Loan` el, `tabEmployee Loan Detail` eld
		WHERE eld.parent = el.name AND el.docstatus = 1 %s 
		ORDER BY eld.employee, el.posting_date"""% conditions_el, as_dict=1)
	frappe.msgprint(loan_list)
	loan_map = {}
	for d in loan_list:
		pass
		#loan_map.setdefault(d.employee)

def get_conditions(filters):
	conditions_emp = ""
	conditions_el = ""

	if filters.get("branch"):
		conditions_emp += " AND emp.branch = '%s'" % filters["branch"]

	if filters.get("department"):
		conditions_emp += " AND emp.department = '%s'" % filters["department"]
				
	if filters.get("employee"):
		conditions_emp += " AND emp.name = '%s'" % filters["employee"]
		
	if filters.get("from_date"):
		conditions_el += "AND el.posting_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions_el += " AND el.posting_date <='%s'" % filters["to_date"]
		
		
	return conditions_emp, conditions_el
