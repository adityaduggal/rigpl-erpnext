# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import math
from frappe.utils import cstr, cint
from frappe import msgprint, _

def execute(filters=None):
	if not filters: filters = {}

	conditions, filters = get_conditions(filters)
	columns = get_columns(filters)
	att_map = get_attendance_list(conditions, filters)[0]
	attendance_list = get_attendance_list(conditions, filters)[1]
	emp_map = get_employee_details()
	holidays = get_holiday_list(conditions, filters)
	total_days = filters["total_days_in_month"]
	data = []
	no_of_employees = len(sorted(att_map))
	#frappe.msgprint(attendance_list)
	for emp in sorted(att_map):
		nos = sum(1 for i in attendance_list if i['day_of_month']==1)
		frappe.msgprint(nos)
	
	for emp in sorted(att_map):
		emp_det = emp_map.get(emp) #emp_det == Employee Details from Employee master
		if not emp_det:
			continue

		row = [emp, emp_det.employee_name]
		row2 = [emp, emp_det.employee_name]
		
		total_p = total_a = total_h = 0.0
		for day in range(total_days):
			stat = ""
			for i in range(len(holidays)):
				if day+1 == holidays[i][0]:
					stat = "Holiday"
			if stat != "Holiday": stat = "Absent"
			date_time = att_map.get(emp).get(day + 1, stat)
			#frappe.msgprint(date_time)
			status = att_map.get(emp).get(day + 1, stat)
			#frappe.msgprint(status)
			status_map = {"Present": "P", "Absent": "A", "Half Day": "HD", "Holiday": "HO"}
			row.append(status_map[status])

			if status == "Present":
				total_p += 1
			elif status == "Absent":
				total_a += 1
			elif status == "Half Day":
				total_p += 0.5
				total_a += 0.5
			elif status == "Holiday":
				total_h += 1
			
			total_s = total_p + math.ceil(total_h/total_days*total_p)

		row += [total_p, total_a, total_s]

		data.append(row)
		data.append(row2)

	return columns, data

def get_columns(filters):
	columns = [
		_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140"
	]

	for day in range(filters["total_days_in_month"]):
		columns.append(cstr(day+1) +"::20")

	columns += [_("Total Present") + ":Float:80", _("Total Absent") + ":Float:80", _("Total Salaried Days") + ":Float:80"]
	return columns

def get_attendance_list(conditions, filters):
	attendance_list = frappe.db.sql("""select at.employee, day(at.att_date) as day_of_month,
		at.status, att.time_type, att.date_time from tabAttendance at, `tabAttendance Time Table` att
		where at.docstatus = 1 AND att.parent = at.name
		%s order by at.employee, at.att_date, att.date_time""" %
		conditions, filters, as_dict=1)
	att_map = {}
	time_map ={}
	#frappe.msgprint(attendance_list)
	for d in attendance_list:
		#frappe.msgprint(d)
		att_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		att_map[d.employee][d.day_of_month] = d.status
		time_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		time_map[d.employee][d.day_of_month] = d.date_time
	#frappe.msgprint(time_map)

	return att_map, attendance_list

def get_conditions(filters):
	if not (filters.get("month") and filters.get("fiscal_year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
		"Dec"].index(filters["month"]) + 1

	from calendar import monthrange
	filters["total_days_in_month"] = monthrange(cint(filters["fiscal_year"].split("-")[-1]),
		filters["month"])[1]

	conditions = " and month(att_date) = %(month)s and fiscal_year = %(fiscal_year)s"

	if filters.get("company"): conditions += " and company = %(company)s"
	if filters.get("employee"): conditions += " and employee = %(employee)s"

	return conditions, filters

def get_employee_details():
	emp_map = frappe._dict()
	for d in frappe.db.sql("""select name, employee_name, designation,
		department, branch, company
		from tabEmployee where docstatus < 2
		and status = 'Active'""", as_dict=1):
		emp_map.setdefault(d.name, d)

	return emp_map

def get_holiday_list(conditions, filters):
	fy = filters.get("fiscal_year")
	month = (filters["month"])
	query = """select day(hol.holiday_date) as holiday from `tabHoliday List` hl, `tabHoliday` hol
		WHERE hl.fiscal_year = "%s" AND hol.parent = hl.name 
		AND MONTH(hol.holiday_date) = %s 
		ORDER BY hol.holiday_date ASC""" %(fy, month)

	hol = frappe.db.sql(query, as_list=1)
	return hol
