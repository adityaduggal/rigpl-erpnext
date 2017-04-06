# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, cstr
from erpnext.hr.doctype.salary_slip.salary_slip import SalarySlip

def execute(filters=None):
	if not filters: filters = {}
	
	emp_lst = get_employee(filters)
	salary_str = get_salary_str(filters, emp_lst)
	columns, earning_types, ded_types, cont_types = get_columns(filters, salary_str)
	data = []
	
	if filters.get("without_salary_structure")<>1:
		ss_earning_map = get_ss_earning_map(salary_str)
		ss_ded_map = get_ss_ded_map(salary_str)
		ss_cont_map = get_ss_cont_map(salary_str)

		for ss in salary_str:
			for emp in emp_lst:
				if ss.employee == emp.name:
					row = [ss.name, ss.from_date, ss.to_date, ss.is_active, emp.name, emp.employee_name]
			tot_earn = 0
			for e in earning_types:
				row.append(ss_earning_map.get(ss.name, {}).get(e))
				add_to_total = frappe.db.sql("""SELECT salary_component_abbr 
					FROM `tabSalary Component`
					WHERE is_earning = 1 AND only_for_deductions <> 1 
					AND salary_component_abbr = '%s'""" %(e), as_list=1)
				if add_to_total:
					tot_earn += flt(ss_earning_map.get(ss.name,{}).get(e))
			row += [tot_earn]
			for d in ded_types:
				row.append(ss_ded_map.get(ss.name, {}).get(d))
			row += [ss.total_deduction, ss.net_pay]
			for c in cont_types:
				row.append(ss_cont_map.get(ss.name, {}).get(c))
			row += [ss.total_ctc]
			data.append(row)
	else:
		conditions_emp, conditions_ss, filters = get_conditions(filters)
		query = """SELECT emp.name, emp.employee_name, ifnull(emp.branch,"-"), 
			ifnull(emp.department,"-"), ifnull(emp.designation,"-"), emp.date_of_joining,
			IFNULL(emp.relieving_date, '2099-12-31')
			FROM `tabEmployee` emp
			WHERE
				emp.name NOT IN (
				SELECT emp.name
				FROM `tabSalary Structure` ss, `tabEmployee` emp, `tabSalary Structure Employee` sse
				WHERE 
				sse.parent = ss.name AND
				emp.name = sse.employee %s
				) AND
				IFNULL(emp.relieving_date,'2099-12-31') > '%s' %s
			ORDER BY emp.date_of_joining""" %(conditions_ss, filters.get("from_date"),conditions_emp)
		data = frappe.db.sql(query, as_list=1)
	
	return columns, data

def get_employee(filters):
	conditions_emp, conditions_ss, filters = get_conditions(filters)
	query = """SELECT * FROM `tabEmployee` emp
		WHERE emp.docstatus =0 %s 
		ORDER BY emp.date_of_joining""" %(conditions_emp)
	emp_lst = frappe.db.sql(query, as_dict=1)
	if emp_lst:
		pass
	else:
		frappe.throw("No Employees in the Given Criterion")
	return emp_lst

def get_salary_str(filters, emp_lst):
	conditions_emp, conditions_ss, filters = get_conditions(filters)
	
	salary_str = frappe.db.sql("""SELECT ss.name, sse.from_date, IFNULL(sse.to_date, '2099-12-31') as to_date, ss.is_active,
		sse.employee, sse.employee_name
		FROM `tabSalary Structure` ss, `tabSalary Structure Employee` sse
		WHERE ss.docstatus = 0 AND ss.name = sse.parent {condition} AND sse.employee IN (%s)
		ORDER BY sse.employee""".format(condition=conditions_ss) %(", ".join(['%s']*len(emp_lst))), \
		tuple([d.name for d in emp_lst]), as_dict=1)
	
	if salary_str:
		pass
	else:
		frappe.throw("No Salary Structure found for given criterion")
	
	return salary_str
	
def get_data_for_eval(ss):
	'''Returns data for evaluating formula'''
	ss_doc = frappe.get_doc("Salary Structure", ss.name)
	eval_data = frappe._dict()
	
	for d in ss_doc.employees:
		if d.employee == ss.employee:
			eval_data.update(frappe.get_doc("Salary Structure Employee", {"employee": d.employee}).as_dict())
	eval_data.update(frappe.get_doc("Employee", d.employee).as_dict())
	eval_data.update(ss_doc.as_dict())

	# set values for components
	salary_components = frappe.get_all("Salary Component", fields=["salary_component_abbr"])
	for salary_component in salary_components:
		eval_data[salary_component.salary_component_abbr] = 0

	return eval_data

def eval_condition_and_formula(d, eval_data):
	try:
		if d.condition:
			if not eval(d.condition, None, eval_data):
				return None
		amount = d.amount
		if d.amount_based_on_formula:
			if d.formula:
				amount = eval(d.formula, None, eval_data)
		if amount:
			eval_data[d.abbr] = amount
		return amount

	except NameError as err:
	    frappe.throw(_("Name error: {0}".format(err)))
	except SyntaxError as err:
	    frappe.throw(_("Syntax error in formula or condition: {0}".format(err)))
	except Exception, e:
	    frappe.throw(_("Error in formula or condition: {0}".format(e)))
	    raise

	
def get_ss_earning_map(salary_str):
	eval_data = get_data_for_eval(salary_str[0])
	ss_earnings = frappe.db.sql("""SELECT sd.parent, sd.salary_component, sd.abbr, sd.amount,
		sd.condition, sd.formula, sd.amount_based_on_formula
		FROM `tabSalary Detail` sd, `tabSalary Component` sc
		WHERE sd.salary_component = sc.name AND 
			sc.is_earning = 1 AND sd.parent in (%s)""" % \
		(', '.join(['%s']*len(salary_str))), tuple([d.name for d in salary_str]), as_dict=1)
	ss_earning_map = {}
	for d in ss_earnings:
		amount = eval_condition_and_formula(d, eval_data)
		ss_earning_map.setdefault(d.parent, frappe._dict()).setdefault(d.abbr, [])
		ss_earning_map[d.parent][d.abbr] = flt(amount)
	return ss_earning_map
	
def get_ss_ded_map(salary_str):
	ss_deductions = frappe.db.sql("""SELECT sd.parent, sd.salary_component, sd.abbr, sd.amount,
		sd.condition, sd.formula, sd.amount_based_on_formula
		FROM `tabSalary Detail` sd, `tabSalary Component` sc
		WHERE sd.salary_component = sc.name AND 
			sc.is_deduction = 1 AND sd.parent in (%s)""" %
		(', '.join(['%s']*len(salary_str))), tuple([d.name for d in salary_str]), as_dict=1)
	
	ss_ded_map = {}
	for d in ss_deductions:
		ss_ded_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
		ss_ded_map[d.parent][d.abbr] = flt(d.amount)
	
	return ss_ded_map
	
def get_ss_cont_map(salary_str):
	ss_contri = frappe.db.sql("""SELECT sd.parent, sd.salary_component, sd.abbr, sd.amount,
		sd.condition, sd.formula, sd.amount_based_on_formula
		FROM `tabSalary Detail` sd,  `tabSalary Component` sc
		WHERE sd.salary_component = sc.name AND 
			sc.is_contribution = 1 AND sd.parent in (%s)""" %
		(', '.join(['%s']*len(salary_str))), tuple([d.name for d in salary_str]), as_dict=1)
	
	ss_cont_map = {}
	for d in ss_contri:
		ss_cont_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
		ss_cont_map[d.parent][d.abbr] = flt(d.amount)
	
	return ss_cont_map
	
def get_columns(filters, salary_str):
	if filters.get("without_salary_structure")<>1:
		columns = [
			_("Salary Structure") + ":Link/Salary Structure:60", _("From Date") + ":Date:80", 
			_("To Date") + ":Date:80", _("Active") + "::40", _("Employee") + ":Link/Employee:80",
			_("Name") + "::150"
		]
		
		earning_types = frappe.db.sql_list("""SELECT DISTINCT sd.abbr, sd.salary_component 
		FROM `tabSalary Detail` sd, `tabSalary Component` sc
		WHERE sc.name = sd.salary_component AND sc.is_earning = 1 AND sd.parent in (%s)""" % 
		(', '.join(['%s']*len(salary_str))), tuple([d.name for d in salary_str]))
		
		ded_types = frappe.db.sql_list("""SELECT DISTINCT sd.abbr, sd.salary_component 
		FROM `tabSalary Detail` sd, `tabSalary Component` sc
		WHERE sc.name = sd.salary_component AND sc.is_deduction = 1 AND sd.parent in (%s)""" % 
		(', '.join(['%s']*len(salary_str))), tuple([d.name for d in salary_str]))
		
		cont_types = frappe.db.sql_list("""SELECT DISTINCT sd.abbr, sd.salary_component 
		FROM `tabSalary Detail` sd, `tabSalary Component` sc
		WHERE sc.name = sd.salary_component AND sc.is_contribution = 1 AND sd.parent in (%s)""" % 
		(', '.join(['%s']*len(salary_str))), tuple([d.name for d in salary_str]))
		
		columns = columns + [(e + ":Currency:80") for e in earning_types] + \
			["Total Earning:Currency:100"] + \
			[(d + ":Currency:80") for d in ded_types] + ["Total Deductions:Currency:100"] + \
			["Net Pay:Currency:100"] + \
			[(c + ":Currency:80") for c in cont_types] + ["Total CTC:Currency:100"]
	else:
		columns = [
			"Employee ID:Link/Employee:100", "Employee Name::200", "Branch::80", "Department::80",
			"Designation::100", "Joining Date:Date:80", "Relieving Date:Date:80"
			]
		earning_types = {}
		ded_types = {}
		cont_types = {}
	
	return columns, earning_types, ded_types, cont_types

def get_conditions(filters):
	conditions_emp = ""
	conditions_ss = ""
	
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
			conditions_ss += " AND ((sse.from_date <='%s' AND IFNULL(sse.to_date, '2099-12-31') <= '%s' AND \
				IFNULL(sse.to_date, '2099-12-31') >= '%s') OR (sse.from_date <= '%s' AND IFNULL(sse.to_date, '2099-12-31') >= '%s'))" % \
				(filters["from_date"], filters["to_date"], filters["from_date"], \
				filters["to_date"], filters["from_date"])

	return conditions_emp, conditions_ss, filters
