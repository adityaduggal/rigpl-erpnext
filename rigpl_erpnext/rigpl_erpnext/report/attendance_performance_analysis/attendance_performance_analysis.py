# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
from __future__ import division
from __future__ import unicode_literals
import frappe
from frappe.utils import getdate


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_entries(filters)

	return columns, data

def get_columns(filters):
	return [
		"Employee#:Link/Employee:100", "Employee Name::150", "TD:Int:50", 
		"Hol:Int:50", "Pres:Int:50", "OT:Float:50",
		"Auth Lea:Int:50", "UnAuth Lea:Int:50", "Att%:Float:100", "Adj Att%:Float:100",
		"Absents:Int:50", "DoJ:Date:80", "DoR:Date:80", "Branch::80", "Department::80", "Designation::80"
		]

def get_entries(filters):
	data = []
	conditions_emp, conditions_att = get_conditions(filters)

	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	total_days = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days + 1

	query = """SELECT emp.name, emp.employee_name, emp.date_of_joining, 
		IFNULL(emp.relieving_date,'2099-12-31') as relieving_date, emp.branch, emp.department, emp.designation,
		(DATEDIFF('%s', '%s')+1) as t_days, 
		
		(SELECT count(hol.name) FROM `tabHoliday` hol , `tabHoliday List` hdl
			WHERE hdl.base_holiday_list = emp.holiday_list AND hol.parent = hdl.name AND
			hol.holiday_date <= '%s' AND hol.holiday_date >= '%s') as holidays, 
		
		(SELECT count(name) FROM `tabAttendance` 
			WHERE employee = emp.name AND docstatus = 1 AND status = 'Present' 
			AND attendance_date <= '%s' AND attendance_date >= '%s') as presents, 
		
		(SELECT sum(overtime) FROM `tabAttendance` 
			WHERE employee = emp.name AND docstatus = 1 AND attendance_date <= '%s' 
			AND attendance_date >= '%s') as overtime,  
		
		(SELECT count(name) FROM `tabAttendance` 
			WHERE employee = emp.name AND docstatus = 1 AND status = 'On Leave' 
			AND attendance_date <= '%s' AND attendance_date >= '%s') as auth_leaves
		
		FROM 
			`tabEmployee` emp
		
		WHERE 
			IFNULL(emp.relieving_date,'2099-12-31') >= '%s' %s""" \
		%(to_date, from_date, to_date, from_date, to_date, from_date, to_date, \
			from_date, to_date, from_date, from_date, conditions_emp)

	data_dict = {}
	data_dict = frappe.db.sql(query, as_dict=1)
	row = []
	for d in data_dict:
		if d.date_of_joining > from_date:
			tot_days = (to_date - d.date_of_joining).days + 1
		elif getdate(d.relieving_date) < to_date:
			tot_days = (getdate(d.relieving_date) - from_date).days + 1
		else:
			tot_days = total_days
		if tot_days != total_days:
			holidays = int(d.holidays/total_days*tot_days)
		else:
			holidays = d.holidays

		ual = tot_days - holidays - d.presents - d.auth_leaves
		if ual < 0:
			ual = 0
			holidays = tot_days - d.presents - d.auth_leaves

		absents = tot_days - d.presents - holidays
		working_days = tot_days - holidays

		if working_days < 1:
			working_days = 1

		att_per = (d.presents/working_days) * 100

		adj_att_per = ((d.presents - ual)/working_days)*100

		row = [d.name, d.employee_name, tot_days, holidays, d.presents, d.overtime, d.auth_leaves, \
			ual, att_per, adj_att_per, absents, d.date_of_joining, d.relieving_date, d.branch, \
			d.department, d.designation]
		data.append(row)
	'''
	for i in range(len(data)):
		for j in range(len(data[i])):
			if data[i][j] is None:
				data[i][j] = 0
		pre = data[i][5]
		hol = data[i][4]
		t_days = data[i][3]
		al = data[i][7]
		ual = t_days - hol - pre - al

		if ual < 0:
			ual = 0
			hol = t_days - pre - al
		
		#deserved holidays = (holidays/total_working_days )*(presents)
		des_hol = (hol/(t_days-hol))* pre
		p_att = ((pre+des_hol)/t_days)*100
		d_att = ((pre+des_hol-ual)/t_days)*100

		data[i][4] = hol
		data[i].insert(8,ual)
		data[i].insert(9,p_att)
		data[i].insert(10,d_att)
		data[i].insert(11, (t_days-hol-pre))
	'''
	return data

def get_conditions(filters):
	conditions_emp = ""
	conditions_att = ""

	if filters.get("branch"):
		conditions_emp += " AND emp.branch = '%s'" % filters["branch"]

	if filters.get("department"):
		conditions_emp += " AND emp.department = '%s'" % filters["department"]
				
	if filters.get("employee"):
		conditions_emp += " AND emp.name = '%s'" % filters["employee"]
		
	if filters.get("from_date"):
		if filters.get("to_date"):
			if filters.get("from_date") >= filters.get("to_date"):
				frappe.throw("From Date Cannot be Greater than or Equal to To Date")
			else:
				conditions_att += " AND att.attendance_date >='%s'" % filters["from_date"]

	if filters.get("to_date"):
		if filters.get("from_date"):
			if filters.get("from_date") >= filters.get("to_date"):
				frappe.throw("From Date Cannot be Greater than or Equal to To Date")
			else:
				conditions_att += " AND att.attendance_date <='%s'" % filters["to_date"]
		
		
	return conditions_emp, conditions_att
