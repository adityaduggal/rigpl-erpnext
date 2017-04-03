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
		"Employee#:Link/Employee:100", "Employee Name::150", "DoJ:Date:80", "TD:Int:50", 
		"T-Hol:Int:50", "T-PR:Int:50", "T-OT:Float:50",
		"T-AL:Int:50", "T-UL:Int:50", "Att%:Float:100", "Ded Att%:Float:100",
		"Total Absent:Int:50"
		]

def get_entries(filters):
	conditions_emp = get_conditions(filters)[0]
	conditions_att = get_conditions(filters)[1]

	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	total_days = getdate(filters.get("to_date")) - getdate(filters.get("from_date"))

	query = """SELECT emp.name, emp.employee_name, emp.date_of_joining,
		(DATEDIFF('%s', '%s')+1) as t_days, 
		
		(SELECT count(hol.name) FROM `tabHoliday` hol , `tabHoliday List` hdl
			WHERE hdl.name = emp.holiday_list AND hol.parent = hdl.name AND
			hol.holiday_date <= '%s' AND hol.holiday_date >= '%s'), 
		
		(SELECT count(name) FROM `tabAttendance` 
			WHERE employee = emp.name AND docstatus = 1 AND attendance_date <= '%s' AND attendance_date >= '%s'), 
		
		(SELECT sum(overtime) FROM `tabAttendance` 
			WHERE employee = emp.name AND docstatus = 1 AND attendance_date <= '%s' AND attendance_date >= '%s'), 
		
		(SELECT sum(total_leave_days) FROM `tabLeave Application` WHERE status = 'Approved' 
			AND docstatus = 1 AND employee = emp.name AND from_date <= '%s') as auth_leave, NULL
		
		FROM 
			`tabEmployee` emp
		
		WHERE 
			IFNULL(emp.relieving_date,'2099-12-31') >= '%s' %s""" \
		%(to_date, from_date, to_date, from_date, to_date, from_date, to_date, \
			from_date, to_date, filters.get("from_date"), conditions_emp)
	
	data = frappe.db.sql(query, as_list=1)
	
	for i in range(len(data)):
		for j in range(len(data[i])):
			if data[i][j] is None:
				data[i][j] = 0
		pre = data[i][5]
		hol = data[i][4]
		t_days = data[i][3]
		al = data[i][7]
		ual = t_days - hol - pre - al
		
		#deserved holidays = (holidays/total_working_days )*(presents)
		des_hol = (hol/(t_days-hol))* pre
		p_att = ((pre+des_hol)/t_days)*100
		d_att = ((pre+des_hol-ual)/t_days)*100

		data[i].insert(8,ual)
		data[i].insert(9,p_att)
		data[i].insert(10,d_att)
		data[i].insert(11, (t_days-hol-pre))
	
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
		conditions_att += " AND att.attendance_date >='%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions_att += " AND att.attendance_date <='%s'" % filters["to_date"]
		
		
	return conditions_emp, conditions_att
