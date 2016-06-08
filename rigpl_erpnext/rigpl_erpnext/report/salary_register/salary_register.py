# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, cstr
from frappe import msgprint, _
from erpnext.hr.doctype.process_payroll.process_payroll import get_month_details

def execute(filters=None):
	if not filters: filters = {}
	conditions_ss, filters, conditions_emp, mdetail = get_conditions(filters)
	emp_lst = get_employee(filters, conditions_emp)
	
	if filters.get("without_salary_slip") <> 1:
		salary_slips = get_salary_slips(filters, conditions_ss, emp_lst)
		columns, earning_types, ded_types = get_columns(salary_slips, filters)
		ss_earning_map = get_ss_earning_map(salary_slips, filters)
		ss_ded_map = get_ss_ded_map(salary_slips)
		ssp_map = get_ssp_map(salary_slips)
		data = []
		for ss in salary_slips:
		
			row = [ss.employee, ss.employee_name, ss.name]
			
			if filters.get("bank_only") == 1 or filters.get("summary") == 1:
				book_gross = 0
				for e in earning_types:
					book_gross += flt(ss_earning_map.get(ss.name, {}).get(e))
				book_ded = 0
				book_net = 0
				
				for d in ded_types:
					book_ded += flt(ss_ded_map.get(ss.name, {}).get(d))
				book_net = book_gross - book_ded

				
			for emp in emp_lst:
				if emp.name == ss.employee:
					row += [emp.branch, emp.department, emp.designation]
									
			if filters.get("summary") <> 1:						
				for e in earning_types:
					row.append(ss_earning_map.get(ss.name, {}).get(e))

			if filters.get("bank_only") == 1:
				row += ["", "", book_gross]
			elif filters.get("summary") == 1:
				row += [ss.rounded_total, book_net, (ss.rounded_total - book_net)]
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
				row += [book_ded, book_net, bank_name, bank_acc, bank_ifsc]
			elif filters.get("summary") == 1:
				row = row
			else:
				row += [ss.total_deduction, ss.net_pay, ss.rounded_total]
			if ssp_map.get(ss.name):
				row += [ssp_map.get(ss.name)]
			else:
				row += ["-"]
			
			data.append(row)
	else:
		columns = [
			_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140",
			_("Branch") + "::100", _("Department") + "::100", _("Designation") + "::100",
			_("Joining Date") + ":Date:80", _("Relieving Date") + ":Date:80"
		]
		
		query = """SELECT emp.name, emp.employee_name, IFNULL(emp.branch,"-"), 
			IFNULL(emp.department,"-"), IFNULL(emp.designation,"-"), emp.date_of_joining,
			IFNULL(emp.relieving_date, '2099-12-31')
			FROM `tabEmployee` emp
			WHERE 
				emp.name NOT IN (
				SELECT emp.name
				FROM `tabSalary Slip` ss, `tabEmployee` emp
				WHERE emp.name = ss.employee AND ss.docstatus = 1 %s
				) AND emp.date_of_joining <= '%s' 
				AND IFNULL(emp.relieving_date, '2099-12-31') >= '%s' %s
			ORDER BY emp.date_of_joining""" %(conditions_ss, mdetail.month_end_date, mdetail.month_end_date, conditions_emp)
		data = frappe.db.sql(query, as_list=1)
	
	return columns, data
	
def get_columns(salary_slips, filters):
	if filters.get("without_salary_slip") == 1:
		columns = [
			_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140",
			_("Branch") + "::140", _("Department") + "::140", _("Designation") + "::140",
		]
		earning_types = []
		ded_types = []
	elif filters.get("summary") == 1:
		columns = [
			_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140",
			_("Salary Slip") + ":Link/Salary Slip:80", 
			_("Branch") + "::80", _("Department") + "::80", _("Designation") + "::80",
			_("Actual Payment") + ":Currency:100", _("Books Payment") + ":Currency:100",
			_("Balance Cash") + ":Currency:100", 
			_("Salary Slip Payment") + ":Link/Salary Slip Payment:150"
		]
	else:
		columns = [
			_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140", 
			_("Salary Slip") + ":Link/Salary Slip:80", _("Branch") + "::80", 
			_("Department") + "::80", _("Designation") + "::80",
		]
	if filters.get("bank_only") == 1 or filters.get("summary") == 1:
		earning_types = frappe.db.sql_list("""SELECT DISTINCT sse.e_type 
			FROM `tabSalary Slip Earning` sse, `tabEarning Type` et
			WHERE sse.e_modified_amount != 0 AND sse.e_type = et.name AND et.books= 1 
			AND sse.parent in (%s)
			ORDER BY sse.idx""" % 
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
			
		ded_types = frappe.db.sql_list("""select DISTINCT ssd.d_type 
			FROM `tabSalary Slip Deduction` ssd, `tabDeduction Type` dt
			WHERE ssd.d_modified_amount != 0 AND dt.name = ssd.d_type 
			AND dt.books = 1 AND ssd.parent in (%s)
			ORDER BY ssd.idx""" % 
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
	else:
		earning_types = frappe.db.sql_list("""SELECT DISTINCT sse.e_type 
			FROM `tabSalary Slip Earning` sse, `tabEarning Type` et
			WHERE sse.e_modified_amount != 0 AND sse.e_type = et.name AND et.books= 0
			AND sse.parent in (%s)
			ORDER BY sse.idx""" % 
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
			
		ded_types = frappe.db.sql_list("""select DISTINCT ssd.d_type 
			FROM `tabSalary Slip Deduction` ssd, `tabDeduction Type` dt
			WHERE ssd.d_modified_amount != 0 AND dt.name = ssd.d_type 
			AND ssd.parent in (%s)
			ORDER BY ssd.idx""" % 
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))		

	if filters.get("summary") <> 1:		
		columns = columns + [(e + ":Currency:90") for e in earning_types] + \
			["Arrear Amt:Currency:90", "Leave Amt:Currency:90", 
			"Gross Pay:Currency:100"] + [(d + ":Currency:90") for d in ded_types] + \
			["Total Deduction:Currency:100", "Net Pay:Currency:100"]
	
	if filters.get("summary") <> 1 and filters.get("bank_only") <> 1 and filters.get("without_salary_slip") <> 1:
		columns = columns + ["Rounded Pay:Currency:100", \
		"Salary Slip Payment:Link/Salary Slip Payment:150"]
	
	if filters.get("bank_only") == 1:
		columns = columns + ["Bank Name::100", "Bank Account #::100", 
		"Bank IFSC::100", "Salary Slip Payment:Link/Salary Slip Payment:150"]

	return columns, earning_types, ded_types

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
		WHERE ss.docstatus = 1  {condition} AND ss.employee IN (%s)
		ORDER BY ss.employee""".format(condition=conditions_ss) %(", ".join(['%s']*len(emp_lst))), \
		tuple([d.name for d in emp_lst]), as_dict=1)
	
	if not salary_slips:
		msgprint(_("No salary slip found for month: ") + cstr(filters.get("month")) + 
			_(" and year: ") + cstr(filters.get("fiscal_year")), raise_exception=1)
	
	return salary_slips
	
def get_ss_earning_map(salary_slips, filters):
	if filters.get("bank_only") == 1:
		ss_earnings = frappe.db.sql("""SELECT sse.parent, sse.e_type, sse.e_modified_amount
			FROM `tabSalary Slip Earning` sse, `tabEarning Type` et
			WHERE et.name = sse.e_type AND et.books = 1 AND sse.parent in (%s)""" %
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	
	elif filters.get("summary")== 1:
		ss_earnings = frappe.db.sql("""SELECT sse.parent, sse.e_type, sse.e_modified_amount
			FROM `tabSalary Slip Earning` sse, `tabEarning Type` et
			WHERE et.name = sse.e_type AND et.books = 1 AND sse.parent in (%s)""" %
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	else:
		ss_earnings = frappe.db.sql("""SELECT sse.parent, sse.e_type, sse.e_modified_amount
			FROM `tabSalary Slip Earning` sse, `tabEarning Type` et
			WHERE et.name = sse.e_type AND et.books = 0 AND sse.parent in (%s)""" %
			(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)

	ss_earning_map = {}
	for d in ss_earnings:
		ss_earning_map.setdefault(d.parent, frappe._dict()).setdefault(d.e_type, [])
		if ss_earning_map[d.parent][d.e_type]:
			ss_earning_map[d.parent][d.e_type] += flt(d.e_modified_amount)
		else:
			ss_earning_map[d.parent][d.e_type] = flt(d.e_modified_amount)

	return ss_earning_map

def get_ss_ded_map(salary_slips):
	ss_deductions = frappe.db.sql("""select parent, d_type, d_modified_amount
		from `tabSalary Slip Deduction` where parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	#frappe.throw(ss_deductions)
	ss_ded_map = {}
	for d in ss_deductions:
		ss_ded_map.setdefault(d.parent, frappe._dict()).setdefault(d.d_type, [])
		if ss_ded_map[d.parent][d.d_type]:
			ss_ded_map[d.parent][d.d_type] += flt(d.d_modified_amount)
		else:
			ss_ded_map[d.parent][d.d_type] = flt(d.d_modified_amount)
	#frappe.throw(ss_ded_map)
	
	return ss_ded_map

def get_ssp_map(salary_slips):
	#frappe.throw(salary_slips)
	ssp = frappe.db.sql("""SELECT ssp.name, sspd.salary_slip
		FROM `tabSalary Slip Payment` ssp, `tabSalary Slip Payment Details` sspd
		WHERE ssp.name = sspd.parent AND ssp.docstatus <> 2 AND sspd.salary_slip in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	ssp_map = {}
	for d in ssp:
		ssp_map.setdefault(d.salary_slip, d.name)
	return ssp_map

	
def get_conditions(filters):
	conditions_ss = ""
	conditions_emp = ""
	fy = filters.get("fiscal_year")
	
	if filters.get("without_salary_slip") == 1:
		if filters.get("bank_only") == 1 or filters.get("summary") == 1:
			frappe.throw("Only one check box Allowed to be Checked")
	elif filters.get("bank_only")==1:
		if filters.get("without_salary_slip") == 1 or filters.get("summary") == 1:
			frappe.throw("Only one check box Allowed to be Checked")
	
	if filters.get("month"):
		month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", 
			"Dec"].index(filters["month"]) + 1

		filters["month"] = month
		conditions_ss += " and ss.month = %s" % month
	mdetail = get_month_details(fy, month)
	
	if filters.get("fiscal_year"): 
		conditions_ss += " and ss.fiscal_year = '%s'" %filters["fiscal_year"]
		
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
		
	return conditions_ss, filters, conditions_emp, mdetail
	
