# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr
from frappe import _
from ....hr_rigpl.utils.attendance_report_utils import get_employees, get_holidays_by_day, get_leaves_by_day, \
	get_month


def execute(filters=None):
	if not filters: filters = {}

	month = get_month(filters)
	columns = get_columns(month.days)
	emp_map = get_employees(filters)
	time_map, ot_map = get_attendance_list(month, filters)
	hol_map = get_holidays_by_day(emp_map, month.from_date, month.to_date)
	la_map = get_leaves_by_day(list(emp_map), month.from_date, month.to_date)

	data = []
	for emp in sorted(time_map):
		emp_det = emp_map.get(emp)
		if not emp_det:
			continue
		data.extend(get_employee_rows(emp, emp_det.employee_name, month.days, time_map[emp], ot_map[emp],
			hol_map.get(emp, {}), la_map.get(emp, {})))
	return columns, data


def get_employee_rows(emp, employee_name, days, punches, overtime, holidays, leaves):
	"""
	The In Time and Out Time rows (1 pair for each punch pair of the busiest day) and the Over Time
	row of 1 employee. A day without attendance shows the holiday, the leave type or X.
	"""
	nos = max(len(day_punches) for day_punches in punches.values())
	rows = [[emp, employee_name, "Out Time" if i % 2 else "In Time"] for i in range(nos)]
	for day in range(1, days + 1):
		for i, row in enumerate(rows):
			if day in punches:
				timing = punches[day].get(i + 1, {}).get(row[2])
				row.append(timing.strftime("%H:%M") if timing else "")
			else:
				row.append(holidays.get(day) or leaves.get(day) or "X")
	ot_row = [emp, employee_name, "Over Time"] + [overtime.get(day, 0) if day in punches else 0
		for day in range(1, days + 1)]
	return rows + [ot_row]


def get_columns(days):
	columns = [
		_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140", _("Time Type") + "::80"
	]
	for day in range(days):
		columns.append(cstr(day+1) +"::50")
	return columns


def get_attendance_list(month, filters):
	"""
	({employee: {day: {row idx: {time type: date_time}}}}, {employee: {day: overtime}}) of the
	submitted Attendance of the month that has punch rows.
	"""
	at = frappe.qb.DocType("Attendance")
	att = frappe.qb.DocType("Attendance Time Table")
	query = (
		frappe.qb.from_(at)
		.join(att).on(att.parent == at.name)
		.select(at.employee, at.attendance_date, att.time_type, att.date_time, att.idx, at.overtime)
		.where((at.docstatus == 1) & at.attendance_date[month.from_date:month.to_date])
		.orderby(at.employee)
		.orderby(at.attendance_date)
	)
	if filters.get("employee"):
		query = query.where(at.employee == filters["employee"])
	time_map, ot_map = {}, {}
	for d in query.run(as_dict=1):
		day = d.attendance_date.day
		time_map.setdefault(d.employee, {}).setdefault(day, {}).setdefault(d.idx, {})[d.time_type] = d.date_time
		ot_map.setdefault(d.employee, {})[day] = d.overtime
	return time_map, ot_map
