# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	emp_map = get_employee_details(filters)
	#frappe.msgprint(str(emp_map))
	open_ded, open_loan = get_opening(filters)
	#frappe.msgprint(str(open_ded))
	loan_given_map = loan_given(filters)
	#frappe.msgprint(str(loan_given_map))
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
		if filters.get("details") != 1:
			if ob>0 or lg>0 or ded>0 or cb>0:
				row = [emp, emp_det.employee_name, emp_det.status, (emp_det.relieving_date or '2099-12-31'), 
					ob, lg, ded, cb]
				data.append(row)
				data.sort()
		
	if filters.get("details") == 1:
		details = get_details(filters)
		row = [filters.get("from_date"), "", "Opening Balance", (ol - od), 0,"", ""]
		data.append(row)
		for i in details:
			row = [i[0],emp, emp_det.employee_name, i[1], i[2], i[3], i[4]]
			data.append(row)
		row = [filters.get("to_date"), "", "Closing Balance", cb, 0, "", ""]
		data.append(row)
		row = [filters.get("to_date"), "", "Adjust", -1*cb, 0, "", ""]
		data.append(row)

	return columns, data

def get_columns(filters):
	if filters.get("details") == 1:
		return [
		"Posting Date:Date:80", "Employee:Link/Employee:100", "Employee Name::180", 
		"Loan Given:Currency:100", "Loan Deducted:Currency:100", 
		"Document::120", "Document Number:Dynamic Link/Document:150"
		]
	else:
		return [
			"Employee:Link/Employee:100", "Employee Name::180", "Status::100",
			"Relieving Date:Date:100", "Opening Balance:Currency:100", 
			"Loan Given:Currency:100", "Loan Deducted:Currency:100", "Closing Balance:Currency:100"
			]
def get_employee_details(filters):
	conditions_emp = get_conditions(filters)[0]
	emp_map = frappe._dict()
	for d in frappe.db.sql("""select emp.name, emp.employee_name, emp.designation,
		emp.department, emp.branch, emp.company, emp.relieving_date, emp.status
		from tabEmployee emp
		WHERE emp.docstatus = 0 %s""" %(conditions_emp), as_dict=1):
		emp_map.setdefault(d.name, d)
	return emp_map

def get_opening(filters):
	open_ded = frappe._dict()
	open_loan = frappe._dict()
	
	dict = frappe.db.sql("""SELECT ss.employee, SUM(ssd.amount) as op_ded
		FROM `tabSalary Slip` ss, `tabSalary Detail` ssd
		WHERE ss.name = ssd.parent AND ss.docstatus =1 AND ssd.employee_loan IS NOT NULL
		AND ss.posting_date < '%s'
		GROUP BY ss.employee""" %filters["from_date"], as_dict=1)
	for d in dict:
		open_ded.setdefault(d.employee, d)
	
	
	for d in frappe.db.sql("""SELECT eld.employee, SUM(eld.loan_amount) as op_loan
		FROM `tabEmployee Advance` el, `tabEmployee Loan Detail` eld
		WHERE el.name = eld.parent AND el.docstatus =1
		AND el.posting_date < '%s'
		GROUP BY eld.employee""" %filters["from_date"], as_dict=1):
		open_loan.setdefault(d.employee, d)

	return open_ded, open_loan

def loan_deducted(filters):
	conditions_ss = get_conditions(filters)[2]
	ss_ded = frappe._dict()
	for d in frappe.db.sql("""SELECT ss.employee, SUM(ssd.amount) as loan_ded
		FROM `tabSalary Slip` ss, `tabSalary Detail` ssd
		WHERE ss.name = ssd.parent AND ss.docstatus = 1 AND ssd.employee_loan IS NOT NULL %s
		GROUP BY ss.employee""" %conditions_ss, as_dict=1):
		ss_ded.setdefault(d.employee,d)
	return ss_ded

def loan_given(filters):
	conditions_el = get_conditions(filters)[1]
	loan_given_map = frappe._dict()
	for d in frappe.db.sql("""SELECT eld.employee, SUM(eld.loan_amount) as loan_given
		FROM `tabEmployee Advance` el, `tabEmployee Loan Detail` eld
		WHERE el.name = eld.parent AND el.docstatus = 1 %s
		GROUP BY eld.employee""" %conditions_el, as_dict=1):
		loan_given_map.setdefault(d.employee,d)

	return loan_given_map

def get_details(filters):
	conditions_emp, conditions_el, conditions_ss = get_conditions(filters)
	loan = frappe.db.sql("""SELECT el.posting_date, eld.loan_amount, 0, 'Employee Advance', el.name
		FROM `tabEmployee Advance` el, `tabEmployee Loan Detail` eld
		WHERE eld.parent = el.name AND el.docstatus = 1 AND 
			eld.employee = '%s' %s ORDER BY el.posting_date""" \
		%(filters.get("employee"), conditions_el), as_list=1)
		
	ded = frappe.db.sql("""SELECT ss.posting_date, 0, SUM(ssd.amount), 'Salary Slip', ss.name
		FROM `tabSalary Slip` ss, `tabSalary Detail` ssd
		WHERE ssd.parent = ss.name AND ss.docstatus = 1 AND 
			ssd.employee_loan IS NOT NULL AND ss.employee = '%s' %s
		GROUP BY ss.name ORDER BY ss.posting_date""" \
		%(filters.get("employee"), conditions_ss), as_list=1)
	
	details = sorted(loan + ded)
	
	return details
	
def get_conditions(filters):
	conditions_emp = ""
	conditions_el = ""
	conditions_ss = ""

	if filters.get("company"):
		conditions_emp += " AND emp.company_registered_with = '%s'" % filters["company"]

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
		
	if filters.get("details"):
		if filters.get("employee"):
			pass
		else:
			frappe.throw("Please select an Employee for getting Loan Details")
		
	return conditions_emp, conditions_el, conditions_ss
