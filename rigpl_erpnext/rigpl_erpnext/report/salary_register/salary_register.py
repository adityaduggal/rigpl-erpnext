# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, cstr
from frappe import msgprint, _
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_month_details

def execute(filters=None):
	if not filters: filters = {}
	conditions_ss, filters, conditions_emp, from_date, to_date = get_conditions(filters)
	emp_lst = get_employee(filters, conditions_emp)
	
	if filters.get("without_salary_slip") <> 1:
		salary_slips = get_salary_slips(filters, conditions_ss, emp_lst)
		columns, earning_types, ded_types, cont_types = get_columns(salary_slips, filters)
		ss_earning_map = get_ss_earning_map(salary_slips, filters)
		ss_ded_map = get_ss_ded_map(salary_slips)
		ss_cont_map = get_ss_cont_map(salary_slips)
		data = []
		for ss in salary_slips:
			
			row = [ss.employee, ss.employee_name, ss.name]
			total_cont = 0
			total_ctc = 0
			
			for c in cont_types:
				total_cont += flt(ss_cont_map.get(ss.name, {}).get(c))

			if filters.get("bank_only") == 1 or filters.get("summary") == 1:
				book_gross = 0
				for e in earning_types:
					book_gross += flt(ss_earning_map.get(ss.name, {}).get(e))
				book_ded = 0
				book_net = 0
				
				for d in ded_types:
					book_ded += flt(ss_ded_map.get(ss.name, {}).get(d))
				book_net = book_gross - book_ded
				if ss.rounded_total > book_net:
					bank_payment = ss.actual_bank_salary
				else:
					bank_payment = ss.actual_bank_salary
				total_ctc = total_cont + book_gross

			for emp in emp_lst:
				if emp.name == ss.employee:
					row += [emp.company_registered_with, emp.branch, emp.department, emp.designation]
									
			if filters.get("summary") <> 1:						
				for e in earning_types:
					row.append(ss_earning_map.get(ss.name, {}).get(e))
					
			if filters.get("bank_only") == 1:
				row += ["", "", book_gross]
			elif filters.get("summary") == 1:
				row += [ss.rounded_total, bank_payment, book_net, (ss.rounded_total - bank_payment)]
			else:
				row += [ss.arrear_amount, ss.leave_encashment_amount, ss.gross_pay]
			if filters.get("summary") <> 1:
				for d in ded_types:
					row.append(ss_ded_map.get(ss.name, {}).get(d))
			
			if filters.get("bank_only") == 1:
				for emp in emp_lst:
					if ss.employee == emp.name:
						bank_name = emp.bank_name
						bank_acc = emp.bank_ac_no
						bank_ifsc = emp.bank_ifsc_code
				row += [book_ded, book_net]
				for c in cont_types:
					row.append(ss_cont_map.get(ss.name, {}).get(c))
					
				row += [total_cont, bank_name, bank_acc, bank_ifsc]
			elif filters.get("summary") == 1:
				row = row
			else:
				row += [ss.total_deduction, ss.net_pay]
				for c in cont_types:
					row.append(ss_cont_map.get(ss.name, {}).get(c))
				row += [total_cont, ss.rounded_total]
			data.append(row)
	else:
		columns = [
			_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140",
			_("Company") + "::50",
			_("Branch") + "::100", _("Department") + "::100", _("Designation") + "::100",
			_("Joining Date") + ":Date:80", _("Relieving Date") + ":Date:80"
		]
		
		query = """SELECT emp.name, emp.employee_name, IFNULL(emp.company_registered_with, "None"),
			IFNULL(emp.branch,"-"), 
			IFNULL(emp.department,"-"), IFNULL(emp.designation,"-"), emp.date_of_joining,
			IFNULL(emp.relieving_date, '2099-12-31')
			FROM `tabEmployee` emp
			WHERE 
				emp.name NOT IN (
				SELECT emp.name
				FROM `tabSalary Slip` ss, `tabEmployee` emp
				WHERE emp.name = ss.employee AND ss.docstatus <> 2 %s
				) AND emp.date_of_joining <= '%s' 
				AND IFNULL(emp.relieving_date, '2099-12-31') >= '%s' %s
			ORDER BY emp.date_of_joining""" %(conditions_ss, to_date, to_date, conditions_emp)
		data = frappe.db.sql(query, as_list=1)
	
	return columns, data
	
def get_columns(salary_slips, filters):
	if filters.get("without_salary_slip") == 1:
		columns = [
			_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140",
			_("Company") + "::50",
			_("Branch") + "::140", _("Department") + "::140", _("Designation") + "::140",
		]
		earning_types = []
		ded_types = []
	elif filters.get("summary") == 1:
		columns = [
			_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140",
			_("Salary Slip") + ":Link/Salary Slip:80", _("Company") + "::50",
			_("Branch") + "::80", _("Department") + "::80", _("Designation") + "::80",
			_("Actual Payment") + ":Currency:100", _("Bank Payment") + ":Currency:100",
			_("Books Payment") + ":Currency:100", _("Balance Cash") + ":Currency:100"
		]
	else:
		columns = [
			_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140", 
			_("Salary Slip") + ":Link/Salary Slip:80", 
			_("Company") + "::50", _("Branch") + "::80", 
			_("Department") + "::80", _("Designation") + "::80",
		]
	if filters.get("bank_only") == 1 or filters.get("summary") == 1:
		earning_types = frappe.db.sql_list("""SELECT DISTINCT sse.salary_component 
			FROM `tabSalary Detail` sse, `tabSalary Component` et
			WHERE sse.amount != 0 AND sse.salary_component = et.name AND et.books= 1
			AND et.is_earning = 1 AND sse.parent in (%s)
			ORDER BY sse.idx""" % 
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
			
		ded_types = frappe.db.sql_list("""select DISTINCT ssd.salary_component 
			FROM `tabSalary Detail` ssd, `tabSalary Component` dt
			WHERE ssd.amount != 0 AND dt.name = ssd.salary_component 
			AND dt.books = 1 AND dt.is_deduction = 1 AND ssd.parent in (%s)
			ORDER BY ssd.idx""" % 
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
	else:
		earning_types = frappe.db.sql_list("""SELECT DISTINCT sse.salary_component 
			FROM `tabSalary Detail` sse, `tabSalary Component` et
			WHERE sse.amount != 0 AND sse.salary_component = et.name AND et.books= 0
			AND et.is_earning = 1 AND sse.parent in (%s)
			ORDER BY sse.idx""" % 
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
			
		ded_types = frappe.db.sql_list("""select DISTINCT ssd.salary_component 
			FROM `tabSalary Detail` ssd, `tabSalary Component` dt
			WHERE ssd.amount != 0 AND dt.name = ssd.salary_component AND dt.is_deduction = 1
			AND ssd.parent in (%s)
			ORDER BY ssd.idx""" % 
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))	
	
	cont_types = frappe.db.sql_list("""select DISTINCT ssd.salary_component 
			FROM `tabSalary Detail` ssd, `tabSalary Component` sc
			WHERE ssd.amount != 0 AND sc.name = ssd.salary_component AND sc.is_contribution = 1
			AND ssd.parent in (%s)
			ORDER BY ssd.idx""" % 
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))	

	if filters.get("summary") <> 1:		
		columns = columns + [(e + ":Currency:90") for e in earning_types] + \
			["Arrear Amt:Currency:90", "Leave Amt:Currency:90", 
			"Gross Pay:Currency:100"] + [(d + ":Currency:90") for d in ded_types] + \
			["Total Deduction:Currency:100", "Net Pay:Currency:100"] + \
			[(c + ":Currency:90") for c in cont_types] + ["Total Contribution:Currency:100"]
	
	
	if filters.get("summary") <> 1 and filters.get("bank_only") <> 1 and filters.get("without_salary_slip") <> 1:
		columns = columns + ["Rounded Pay:Currency:100"]
	
	if filters.get("bank_only") == 1:
		columns = columns + ["Bank Name::100", "Bank Account #::100", 
		"Bank IFSC::100"]

	return columns, earning_types, ded_types, cont_types

def get_employee(filters, conditions_emp):
	emp_lst = frappe.db.sql("""SELECT *
		FROM `tabEmployee` emp 
		WHERE emp.docstatus =0 %s ORDER BY emp.date_of_joining""" \
		%(conditions_emp), as_dict=1)
	emp_map = {}
	
	if emp_lst:
		pass
	else:
		frappe.throw("No Employees in the Given Criterion")
	return emp_lst
	
def get_salary_slips(filters, conditions_ss, emp_lst):

	salary_slips = frappe.db.sql("""SELECT * 
		FROM `tabSalary Slip` ss
		WHERE ss.docstatus <> 2  {condition} AND ss.employee IN (%s)
		ORDER BY ss.employee""".format(condition=conditions_ss) %(", ".join(['%s']*len(emp_lst))), \
		tuple([d.name for d in emp_lst]), as_dict=1)
	
	if not salary_slips:
		msgprint(_("No salary slip found between dates"), raise_exception=1)
	
	return salary_slips
	
def get_ss_earning_map(salary_slips, filters):
	if filters.get("bank_only") == 1:
		ss_earnings = frappe.db.sql("""SELECT sse.parent, sse.salary_component, sse.amount
			FROM `tabSalary Detail` sse, `tabSalary Component` et
			WHERE et.name = sse.salary_component AND et.books = 1 
			AND et.is_earning = 1 AND sse.parent in (%s)""" %
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	
	elif filters.get("summary")== 1:
		ss_earnings = frappe.db.sql("""SELECT sse.parent, sse.salary_component, sse.amount
			FROM `tabSalary Detail` sse, `tabSalary Component` et
			WHERE et.name = sse.salary_component AND et.books = 1 AND 
			et.is_earning = 1 AND sse.parent in (%s)""" %
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	else:
		ss_earnings = frappe.db.sql("""SELECT sse.parent, sse.salary_component, sse.amount
			FROM `tabSalary Detail` sse, `tabSalary Component` et
			WHERE et.name = sse.salary_component AND et.books = 0 
			AND et.is_earning = 1 AND sse.parent in (%s)""" %
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)

	ss_earning_map = {}
	for d in ss_earnings:
		ss_earning_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
		if ss_earning_map[d.parent][d.salary_component]:
			ss_earning_map[d.parent][d.salary_component] += flt(d.amount)
		else:
			ss_earning_map[d.parent][d.salary_component] = flt(d.amount)

	return ss_earning_map

def get_ss_ded_map(salary_slips):
	ss_deductions = frappe.db.sql("""select parent, salary_component, amount
		from `tabSalary Detail` where parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	ss_ded_map = {}
	for d in ss_deductions:
		ss_ded_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
		if ss_ded_map[d.parent][d.salary_component]:
			ss_ded_map[d.parent][d.salary_component] += flt(d.amount)
		else:
			ss_ded_map[d.parent][d.salary_component] = flt(d.amount)

	
	return ss_ded_map
	
def get_ss_cont_map(salary_slips):
	ss_contributions = frappe.db.sql("""select parent, salary_component, amount
		from `tabSalary Detail` where parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([c.name for c in salary_slips]), as_dict=1)
	ss_cont_map = {}
	for c in ss_contributions:
		ss_cont_map.setdefault(c.parent, frappe._dict()).setdefault(c.salary_component, [])
		if ss_cont_map[c.parent][c.salary_component]:
			ss_cont_map[c.parent][c.salary_component] += flt(c.amount)
		else:
			ss_cont_map[c.parent][c.salary_component] = flt(c.amount)
	
	return ss_cont_map
	
def get_conditions(filters):
	conditions_ss = ""
	conditions_emp = ""
	
	
	to_date = filters.get("to_date")
	
	if filters.get("from_date"):
		from_date = filters.get("from_date")
		conditions_ss += " AND ss.start_date >= '%s'" %filters["from_date"]
	
	if filters.get("to_date"):
		from_date = filters.get("to_date")
		conditions_ss += " AND ss.end_date <= '%s'" %filters["to_date"]

	
	if filters.get("without_salary_slip") == 1:
		if filters.get("bank_only") == 1 or filters.get("summary") == 1:
			frappe.throw("Only one check box Allowed to be Checked")
	elif filters.get("bank_only")==1:
		if filters.get("without_salary_slip") == 1 or filters.get("summary") == 1:
			frappe.throw("Only one check box Allowed to be Checked")
					
	if filters.get("employee"): 
		conditions_ss += " and ss.employee = '%s'" % filters["employee"]
		conditions_emp += " AND emp.name = '%s'" % filters["employee"]
	
	if filters.get("branch"):
		conditions_emp += " AND emp.branch = '%s'" % filters["branch"]
		
	if filters.get("department"):
		conditions_emp += " AND emp.department = '%s'" % filters["department"]
		
	if filters.get("designation"):
		conditions_emp += " AND emp.designation = '%s'" % filters["designation"]
		
	if filters.get("company_registered_with"):
		conditions_emp += " AND emp.company_registered_with = '%s'" % filters["company_registered_with"]
	
	if filters.get("salary_mode"):
		conditions_emp += " AND emp.salary_mode = '%s'" % filters["salary_mode"]
		
	return conditions_ss, filters, conditions_emp, from_date, to_date
	
