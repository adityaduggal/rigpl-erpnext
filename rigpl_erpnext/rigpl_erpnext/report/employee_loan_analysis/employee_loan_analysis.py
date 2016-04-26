# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	emp_map = get_employee_details(filters)
	open_ded = get_opening(filters)[0]
	open_loan = get_opening(filters)[1]
	loan_given_map = loan_given(filters)
	ss_ded = loan_deducted(filters)
	
	data = []
	for emp in emp_map:
		emp_det = emp_map.get(emp)
		if emp in open_loan:
			ol = open_loan.get(emp).op_loan
		else:
			ol = 0
		
		if emp in open_ded:
			od = open_ded.get(emp).op_ded
		else:
			od = 0
			
		if emp in ss_ded:
			ded = ss_ded.get(emp).loan_ded

		else:
			ded = 0
			
		if emp in loan_given_map:
			lg = loan_given_map.get(emp).loan_given
		else:
			lg = 0
		ob = ol - od
		cb = ob + lg - ded
		if ol > 0 or od > 0 or lg > 0 or ded > 0:
			row = [emp, emp_det.employee_name, ol, od, ob, lg, ded, cb]
			data.append(row)
			data.sort()

	return columns, data

def get_columns(filters):
	return [
		"Employee:Link/Employee:100", "Employee Name::180", "Loan Opening:Currency:100",
		"Deductions Opening:Currency:100", "Balance Opening:Currency:100", 
		"Given Loan:Currency:100", "Loan Deducted:Currency:100", "Balance Closing:Currency:100"
		]
def get_employee_details(filters):
	conditions_emp = get_conditions(filters)[0]
	emp_map = frappe._dict()
	for d in frappe.db.sql("""select emp.name, emp.employee_name, emp.designation,
		emp.department, emp.branch, emp.company
		from tabEmployee emp
		WHERE IFNULL(emp.relieving_date, '2099-12-31') >= '%s' 
		%s""" %(filters["from_date"], conditions_emp), as_dict=1):
		emp_map.setdefault(d.name, d)
	return emp_map

def get_opening(filters):
	open_ded = frappe._dict()
	open_loan = frappe._dict()
	
	for d in frappe.db.sql("""SELECT ss.employee, SUM(ssd.d_modified_amount) as op_ded
		FROM `tabSalary Slip` ss, `tabSalary Slip Deduction` ssd
		WHERE ss.name = ssd.parent AND ss.docstatus =1 AND ssd.employee_loan IS NOT NULL
		AND ss.posting_date < '%s'
		GROUP BY ss.employee""" %filters["from_date"], as_dict=1):
		open_ded.setdefault(d.employee, d)
	
	for d in frappe.db.sql("""SELECT eld.employee, SUM(eld.loan_amount) as op_loan
		FROM `tabEmployee Loan` el, `tabEmployee Loan Detail` eld
		WHERE el.name = eld.parent AND el.docstatus =1
		AND el.posting_date < '%s'
		GROUP BY eld.employee""" %filters["from_date"], as_dict=1):
		open_loan.setdefault(d.employee, d)

	return open_ded, open_loan

def loan_deducted(filters):
	conditions_ss = get_conditions(filters)[2]
	ss_ded = frappe._dict()
	for d in frappe.db.sql("""SELECT ss.employee, SUM(ssd.d_modified_amount) as loan_ded
		FROM `tabSalary Slip` ss, `tabSalary Slip Deduction` ssd
		WHERE ss.name = ssd.parent AND ss.docstatus = 1 AND ssd.employee_loan IS NOT NULL %s
		GROUP BY ss.employee""" %conditions_ss, as_dict=1):
		ss_ded.setdefault(d.employee,d)
	return ss_ded

def loan_given(filters):
	conditions_el = get_conditions(filters)[1]
	loan_given_map = frappe._dict()
	for d in frappe.db.sql("""SELECT eld.employee, SUM(eld.loan_amount) as loan_given
		FROM `tabEmployee Loan` el, `tabEmployee Loan Detail` eld
		WHERE el.name = eld.parent AND el.docstatus = 1 %s
		GROUP BY eld.employee""" %conditions_el, as_dict=1):
		loan_given_map.setdefault(d.employee,d)

	return loan_given_map

def get_conditions(filters):
	conditions_emp = ""
	conditions_el = ""
	conditions_ss = ""

	if filters.get("branch"):
		conditions_emp += " AND emp.branch = '%s'" % filters["branch"]

	if filters.get("department"):
		conditions_emp += " AND emp.department = '%s'" % filters["department"]
				
	if filters.get("employee"):
		conditions_emp += " AND emp.name = '%s'" % filters["employee"]
		
	if filters.get("from_date"):
		conditions_el += "AND el.posting_date >= '%s'" % filters["from_date"]
		conditions_ss += "AND ss.posting_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions_el += " AND el.posting_date <='%s'" % filters["to_date"]
		conditions_ss += " AND ss.posting_date <='%s'" % filters["to_date"]
		
		
	return conditions_emp, conditions_el, conditions_ss
