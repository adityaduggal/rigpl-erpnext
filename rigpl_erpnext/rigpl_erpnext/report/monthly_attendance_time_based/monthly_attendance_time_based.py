# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, getdate
from frappe import msgprint, _
from calendar import monthrange
from datetime import datetime
from erpnext.hr.doctype.process_payroll.process_payroll import get_month_details

def execute(filters=None):
	if not filters: filters = {}

	conditions, filters, conditions_hol, conditions_la, conditions_emp = get_conditions(filters)
	columns = get_columns(filters)
	att_map, time_map, ot_map, attendance_list, no_rows = get_attendance_list(conditions, filters)
	emp_map = get_employee_details(conditions_emp)
	hol_map = get_holiday_list(conditions_hol)
	la_map = get_leave_application(conditions_la, filters)
	data = []
	
	for emp in sorted(att_map):
		emp_det = emp_map.get(emp)
		if not emp_det:
			continue
		row0 = [emp, emp_det.employee_name, "In Time"]
		row2 = [emp, emp_det.employee_name, "Out Time"]
		row3 = [emp, emp_det.employee_name, "Over Time"]
		
		rows = {}
		
		key = max(no_rows.get(emp), key=no_rows.get)
		nos = no_rows.get(emp).get(key)
		
		for i in range(nos+1):
			if i <> nos:
				if is_odd(i):
					rows["row{0}".format(i)] = row2[:]
				else:
					rows["row{0}".format(i)] = row0[:]
			else:
				rows["row{0}".format(i)] = row3[:]

		for day in range(filters["total_days_in_month"]):
			for np in range(nos+1):
				row_no = "row" + `np`
				tt = rows[row_no][2]
				if np < nos:
					if time_map.get(emp).get(day+1,"None") <> "None":
					#above if statement checks if there is any attendance for the employee on that day
						if time_map.get(emp).get(day+1, "None").get(np + 1, "None") <> "None":
						#above if statement checks if there is any Punch Data if there is attendance
							timing = time_map.get(emp).get(day + 1, "None").get(np + 1, "None")		
							timing_hrs = timing[tt].time().isoformat()
							timing_hrs = timing[tt].strftime("%H:%M")
							rows[row_no].append(timing_hrs)
						else:
						#attendance is there but there is no punch data
							rows[row_no].append("")
					else:
						#here there is no attendance for emp for a day, so check if the day is
						#HOLIDAY LIST or IN LEAVE APPLICATION
						if hol_map and hol_map.get(emp) and hol_map.get(emp).get(day+1, "None") <> "None":
							hol = hol_map.get(emp).get(day+1, "None")
							rows[row_no].append(hol)
						elif la_map and la_map.get(emp) and la_map.get(emp).get(day+1, "None")<> "None":
							la = la_map.get(emp).get(day+1, "None")
							rows[row_no].append(la)
						else:
							rows[row_no].append("X")
				else:
					if ot_map.get(emp).get(day+1, "None") <> "None": 
					#Checks if the attendance for that day exists
						ot = ot_map.get(emp).get(day+1, "")
						rows[row_no].append(ot)
					else:
						rows[row_no].append(0)
		for d in rows:
			data.append(rows[d])

	return columns, data

def get_columns(filters):
	columns = [
		_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140", _("Time Type") + "::80"
	]

	for day in range(filters["total_days_in_month"]):
		columns.append(cstr(day+1) +"::50")
		
	return columns

def get_attendance_list(conditions, filters):
	attendance_list = frappe.db.sql("""select at.employee, day(at.attendance_date) as day_of_month,
		at.status, att.time_type, att.date_time, att.idx, at.overtime
		FROM tabAttendance at, `tabAttendance Time Table` att
		WHERE at.docstatus = 1 AND att.parent = at.name %s 
		ORDER BY at.employee, at.attendance_date""" %
		conditions, filters, as_dict=1)
	att_map = {}
	time_map = {}
	ot_map = {}
	no_rows = {}
	
	for d in attendance_list:
		att_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		att_map[d.employee][d.day_of_month] = d.status
		
		time_map.setdefault(d.employee, frappe._dict()).\
			setdefault(d.day_of_month, frappe._dict()).\
			setdefault(d.idx, frappe._dict()).setdefault(d.time_type, "")
		time_map[d.employee][d.day_of_month][d.idx][d.time_type] = d.date_time
		
		ot_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		ot_map[d.employee][d.day_of_month] = d.overtime
		

	for d in attendance_list:
		no_rows.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		no_rows[d.employee][d.day_of_month] = len((time_map[d.employee][d.day_of_month]))
		
	return att_map, time_map, ot_map, attendance_list, no_rows

def get_conditions(filters):
	
	conditions_la = ""
	conditions_hol = ""
	conditions_emp = ""
	
	if not (filters.get("month") and filters.get("year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
		"Dec"].index(filters.month) + 1

	filters["total_days_in_month"] = monthrange(cint(filters.year), filters.month)[1]
	
	from_date = str(filters["year"]) + "-" + str(filters["month"]) + "-" + str(1)
	to_date = str(filters["year"]) + "-" + str(filters["month"]) + "-" + str(filters["total_days_in_month"])

	conditions = " and month(at.attendance_date) = %(month)s and year(at.attendance_date) = %(year)s"
	
	conditions_hol = "AND ho.holiday_date >= '%s' AND ho.holiday_date <= '%s'" %(from_date, to_date)
	
	if filters.get("employee"):
		conditions += " and at.employee = %(employee)s"
		conditions_hol += " AND emp.name = '%s'" %filters["employee"]
		conditions_la += " AND emp.name = '%s'" %filters["employee"]
		conditions_emp += " AND emp.name = '%s'" %filters["employee"]
	
	if filters.get("branch"):
		conditions_hol += " AND emp.branch = '%s'" %filters["branch"]
		conditions_la += " AND emp.branch = '%s'" %filters["branch"]
		conditions_emp += " AND emp.branch = '%s'" %filters["branch"]
		
	if filters.get("department"):
		conditions_hol += " AND emp.department = '%s'" %filters["department"]
		conditions_la += " AND emp.department = '%s'" %filters["department"]
		conditions_emp += " AND emp.department = '%s'" %filters["department"]
		
	if filters.get("designation"):
		conditions_hol += " AND emp.designation = '%s'" %filters["designation"]
		conditions_la += " AND emp.designation = '%s'" %filters["designation"]
		conditions_emp += " AND emp.designation = '%s'" %filters["designation"]

	return conditions, filters, conditions_hol, conditions_la, conditions_emp

def get_employee_details(conditions_emp):
	
	emp_map = frappe._dict()
	for d in frappe.db.sql("""SELECT emp.name, emp.employee_name, emp.designation,
		emp.department, emp.branch, emp.company
		FROM tabEmployee emp
		WHERE emp.docstatus = 0 %s""" % conditions_emp, as_dict=1):
		emp_map.setdefault(d.name, d)

	return emp_map

def get_leave_application(conditions_la, filters):
	la_map = frappe._dict()
	la = []

	for day in range(filters["total_days_in_month"]):
		date = str(filters["year"]) + "-" + str(filters["month"]) + "-" + str(day+1)
	
		query = """SELECT emp.name as employee, %s as day_of_month, la.leave_type
			FROM `tabLeave Application` la, `tabEmployee` emp
			WHERE la.employee = emp.name AND la.status = 'Approved' 
				AND la.docstatus = 1 AND la.from_date <= '%s' 
				AND la.to_date >= '%s' %s""" %((day+1), date, date, conditions_la)
		la2 = (frappe.db.sql(query, as_dict=1))
		if la2:
			for d in la2:
				la.append(d)
		for d in la:
			la_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
			la_map[d.employee][d.day_of_month] = d.leave_type
	return la_map

def get_holiday_list(conditions_hol):
	hol_map = frappe._dict()
	query = """SELECT emp.name as employee , day(ho.holiday_date)  as day_of_month, ho.description
		FROM `tabEmployee` emp, `tabHoliday List` hol, `tabHoliday` ho
		WHERE emp.holiday_list = hol.name AND ho.parent = hol.name %s""" %(conditions_hol)
	holidays = frappe.db.sql(query, as_dict=1)
	for d in holidays:
		hol_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		hol_map[d.employee][d.day_of_month] = d.description

	return hol_map
	
@frappe.whitelist()
def get_attendance_years():
	year_list = frappe.db.sql_list("""select distinct YEAR(at.attendance_date) from tabAttendance at 
		ORDER BY YEAR(at.attendance_date) DESC""")
	if not year_list:
		year_list = [getdate().year]

	return "\n".join(str(year) for year in year_list)
	
def is_odd(a):
	return bool(a - ((a>>1)<<1))
