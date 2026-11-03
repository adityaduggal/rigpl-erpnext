# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr
from frappe import _
from ....hr_rigpl.utils.attendance_report_utils import get_employees, get_holidays_by_day, get_leaves_by_day, \
	get_month

STATUS_MAP = {"Present": "P", "Absent": "A", "Half Day": "H", "Holiday": "HO", "Unauthorized Leave": "X",
	"Authorized Leave": "L", "On Leave": "L"}


def execute(filters=None):
	if not filters: filters = {}

	month = get_month(filters)
	columns = get_columns(month.days)
	emp_map = get_employees(filters)
	att_map = get_attendance_list(month, filters)
	hol_map = get_holidays_by_day(emp_map, month.from_date, month.to_date)
	la_map = get_leaves_by_day(list(emp_map), month.from_date, month.to_date)

	data = []
	for emp in sorted(att_map):
		emp_det = emp_map.get(emp)
		if not emp_det:
			continue
		row = [emp, emp_det.employee_name]
		total_p = total_a = 0.0
		for day in range(1, month.days + 1):
			status = att_map[emp].get(day)
			row.append(get_day_code(status, day in hol_map.get(emp, {}), day in la_map.get(emp, {})))
			if status == "Present":
				total_p += 1
			elif status == "Absent":
				total_a += 1
			elif status == "Half Day":
				total_p += 0.5
				total_a += 0.5
		data.append(row + [total_p, total_a])

	return columns, data


def get_day_code(status, is_holiday, on_leave):
	"""The code of a day: the Attendance status, else Holiday, else Authorized or Unauthorized Leave."""
	if status:
		return STATUS_MAP.get(status, "")
	if is_holiday:
		return STATUS_MAP["Holiday"]
	return STATUS_MAP["Authorized Leave"] if on_leave else STATUS_MAP["Unauthorized Leave"]


def get_columns(days):
	columns = [
		_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140"
	]
	for day in range(days):
		columns.append(cstr(day+1) +"::20")
	columns += [_("Total Present") + "::80", _("Total Absent") + "::80"]
	return columns


def get_attendance_list(month, filters):
	"""{employee: {day of month: status}} of the submitted Attendance of the month."""
	at = frappe.qb.DocType("Attendance")
	query = (
		frappe.qb.from_(at)
		.select(at.employee, at.attendance_date, at.status)
		.where((at.docstatus == 1) & at.attendance_date[month.from_date:month.to_date])
		.orderby(at.employee)
		.orderby(at.attendance_date)
	)
	if filters.get("employee"):
		query = query.where(at.employee == filters["employee"])
	att_map = {}
	for d in query.run(as_dict=1):
		att_map.setdefault(d.employee, {})[d.attendance_date.day] = d.status
	return att_map
