# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, getdate
from frappe import msgprint, _
from calendar import monthrange

def execute(filters=None):
	if not filters: filters = {}

	conditions, filters, conditions_hol = get_conditions(filters)
	columns = get_columns(filters)
	att_map = get_attendance_list(conditions, filters)
	emp_map = get_employee_details()

	data = []
	for emp in sorted(att_map):
		emp_det = emp_map.get(emp)
		if not emp_det:
			continue

		row = [emp, emp_det.employee_name]

		total_p = total_a = 0.0
		for day in range(filters["total_days_in_month"]):
			status = att_map.get(emp).get(day + 1, "None")
			status_map = {"Present": "P", "Absent": "A", "Half Day": "H", "None": ""}
			row.append(status_map[status])

			if status == "Present":
				total_p += 1
			elif status == "Absent":
				total_a += 1
			elif status == "Half Day":
				total_p += 0.5
				total_a += 0.5

		row += [total_p, total_a]
		data.append(row)

	return columns, data

def get_columns(filters):
	columns = [
		_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140"
	]

	for day in range(filters["total_days_in_month"]):
		columns.append(cstr(day+1) +"::20")

	columns += [_("Total Present") + ":Float:80", _("Total Absent") + ":Float:80"]
	return columns

def get_attendance_list(conditions, filters):
	attendance_list = frappe.db.sql("""select employee, day(att_date) as day_of_month,
		status from tabAttendance where docstatus = 1 %s order by employee, att_date""" %
		conditions, filters, as_dict=1)
	holiday_list = get_holidays(conditions, filters)
	att_map = {}
	for d in attendance_list:
		#frappe.msgprint(att_map)
		att_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		att_map[d.employee][d.day_of_month] = d.status

	return att_map

def get_holidays(conditions_hol,filters):

	holiday_list = frappe.db.sql("""SELECT description, day(holiday_date) as day_of_month
		FROM `tabHoliday`""", conditions_hol, filters, as_dict=1)
	frappe.msgprint(holiday_list)
	return holiday_list

def get_conditions(filters):
	if not (filters.get("month") and filters.get("year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
		"Dec"].index(filters.month) + 1

	filters["total_days_in_month"] = monthrange(cint(filters.year), filters.month)[1]

	conditions = " and month(att_date) = %(month)s and year(att_date) = %(year)s"
	conditions_hol = " AND month(holiday_date) = %(month)s AND year(holiday_date) = %(year)s"

	if filters.get("employee"): conditions += " and employee = %(employee)s"

	return conditions, filters, conditions_hol

def get_employee_details():
	emp_map = frappe._dict()
	for d in frappe.db.sql("""select name, employee_name, designation,
		department, branch, company
		from tabEmployee""", as_dict=1):
		emp_map.setdefault(d.name, d)

	return emp_map