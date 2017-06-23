# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _

def execute(filters=None):
	non_zero = get_conditions(filters)[2]
	columns = get_columns(filters)
	emp_map = get_employee_details(filters)
	open_dict, between_dict = get_opening(filters)
	
	data = []
	for emp in emp_map:
		emp_det = emp_map.get(emp)
		if emp in open_dict:
			open_bal = open_dict.get(emp).opening
		else:
			open_bal = 0
		
		if emp in between_dict:
			bet_inc = between_dict.get(emp).bw_credit
			bet_dec = between_dict.get(emp).bw_debit
		else:
			bet_inc = 0
			bet_dec = 0
		
		closing = open_bal + bet_inc - bet_dec
		
		if non_zero == 1:
			if open_bal <>0 or bet_inc <>0 or bet_dec <> 0 or closing <>0:
				row = [emp, emp_det.employee_name, emp_det.company_registered_with, \
					emp_det.branch, emp_det.department, emp_det.designation, \
					emp_det.date_of_joining, emp_det.relieving_date, open_bal, bet_inc, \
					bet_dec, closing]
				data.append(row)
				data.sort()
		else:
			row = [emp, emp_det.employee_name, emp_det.company_registered_with, \
				emp_det.branch, emp_det.department, emp_det.designation, \
				emp_det.date_of_joining, emp_det.relieving_date, open_bal, bet_bal, closing]
			data.append(row)
			data.sort()
			
		
		
	return columns, data
	
def get_columns(filters):
	columns = [
		_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140",
		_("Company") + "::50", _("Branch") + "::100", _("Department") + "::100", 
		_("Designation") + "::100", _("Joining Date") + ":Date:80", _("Relieving Date") + ":Date:80",
		_("Opening") + ":Currency:100", _("Period Increase") + ":Currency:100",
		_("Period Decrease") + ":Currency:100", _("Closing") + ":Currency:100"
	]
	return columns

def get_employee_details(filters):
	conditions_emp = get_conditions(filters)[0]
	emp_map = frappe._dict()
	for d in frappe.db.sql("""select emp.name, emp.employee_name, emp.designation,
		emp.department, emp.branch, emp.company_registered_with, emp.date_of_joining,
		emp.relieving_date
		from tabEmployee emp
		WHERE emp.docstatus = 0 %s""" %(conditions_emp), as_dict=1):
		emp_map.setdefault(d.name, d)

	return emp_map

def get_opening(filters):
	open_dict = frappe._dict()
	between_dict = frappe._dict()
	conditions_gl = get_conditions(filters)[1]
	op_dict = frappe.db.sql("""SELECT gl.party, (SUM(gl.credit) - SUM(gl.debit)) as opening
		FROM `tabGL Entry` gl
		WHERE gl.party_type = 'Employee' AND gl.posting_date < '%s'
		GROUP BY gl.party""" %(filters["from_date"]), as_dict=1)

	bw_dict = frappe.db.sql("""SELECT gl.party, SUM(gl.credit) as bw_credit,
		SUM(gl.debit) as bw_debit
		FROM `tabGL Entry` gl
		WHERE gl.party_type = 'Employee' AND gl.posting_date >= '%s' AND gl.posting_date <= '%s'
		GROUP BY gl.party""" %(filters["from_date"], filters["to_date"]), as_dict=1)

	for d in bw_dict:
		between_dict.setdefault(d.party, d)
		
	for d in op_dict:
		open_dict.setdefault(d.party,d)
	return open_dict, between_dict

def get_conditions(filters):
	conditions_gl = ""
	conditions_emp = ""
	non_zero = 0
	
	if filters.get("non_zero"):
		non_zero = 1

	if filters.get("from_date"):
		conditions_gl += " AND posting_date <= '%s'" %filters["from_date"]

	if filters.get("to_date"):
		conditions_gl += " AND posting_date <= '%s'" %filters["to_date"]
					
	if filters.get("employee"): 
		conditions_emp += " AND emp.name = '%s'" % filters["employee"]
	
	if filters.get("branch"):
		conditions_emp += " AND emp.branch = '%s'" % filters["branch"]
		
	if filters.get("department"):
		conditions_emp += " AND emp.department = '%s'" % filters["department"]
		
	if filters.get("designation"):
		conditions_emp += " AND emp.designation = '%s'" % filters["designation"]
		
	if filters.get("company_registered_with"):
		conditions_emp += " AND emp.company_registered_with = '%s'" % filters["company_registered_with"]
	return conditions_emp, conditions_gl, non_zero
