# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import getdate

NO_END = "2099-12-31"
# filter: Employee field
EMPLOYEE_FILTERS = {"employee": "name", "branch": "branch", "department": "department", "designation": "designation"}


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_entries(filters)

	return columns, data


def get_columns(filters):
	if filters.get("without_roster")!=1:
		return [
			"ID:Link/Shift Assignment:80", "From Date:Date:80", "To Date:Date:80",
			"Shift:Link/Shift Type:100", "Shift Name::150",
			"Employee ID:Link/Employee:100", "Employee Name::200", "Branch::80", "Department::80",
			"Designation::100", "Shift In:Time:100", "Shift Out:Time:100", "Hours Required::80"
			]
	else:
		return [
			"Employee ID:Link/Employee:100", "Employee Name::200", "Branch::80", "Department::80",
			"Designation::100", "Joining Date:Date:80", "Relieving Date:Date:80"
			]


def get_entries(filters):
	"""
	The submitted, Active Shift Assignments that overlap the period, or with Without Roster the
	employees in service in the period that have none. tabRoster ended in 2020, so the report reads
	Shift Assignment (#187).
	"""
	from_date, to_date = getdate(filters.get("from_date")), getdate(filters.get("to_date"))
	if from_date > to_date:
		frappe.throw("From Date cannot be after To Date", title="Wrong Period")
	emp = frappe.qb.DocType("Employee")
	sa = frappe.qb.DocType("Shift Assignment")
	assigned = (
		(sa.docstatus == 1) & (sa.status == "Active") & (sa.start_date <= to_date)
		& (IfNull(sa.end_date, NO_END) >= from_date)
	)
	if filters.get("without_roster") == 1:
		with_shift = frappe.qb.from_(sa).select(sa.employee).where(assigned)
		query = (
			frappe.qb.from_(emp)
			.select(emp.name, emp.employee_name, IfNull(emp.branch, "-"), IfNull(emp.department, "-"),
				IfNull(emp.designation, "-"), emp.date_of_joining, IfNull(emp.relieving_date, NO_END))
			.where(emp.name.notin(with_shift))
			.where((emp.date_of_joining < to_date) & (IfNull(emp.relieving_date, NO_END) > from_date))
			.orderby(emp.date_of_joining)
		)
	else:
		sh = frappe.qb.DocType("Shift Type")
		query = (
			frappe.qb.from_(sa)
			.join(sh).on(sh.name == sa.shift_type)
			.join(emp).on(emp.name == sa.employee)
			.select(sa.name, sa.start_date, sa.end_date, sa.shift_type, sh.name, emp.name, emp.employee_name,
				IfNull(emp.branch, "-"), IfNull(emp.department, "-"), IfNull(emp.designation, "-"), sh.start_time,
				sh.end_time, sh.hours_required_per_day)
			.where(assigned)
			.orderby(sa.start_date)
			.orderby(sa.end_date)
			.orderby(emp.date_of_joining)
		)
		if filters.get("shift"):
			query = query.where(sa.shift_type == filters["shift"])
	for key, field in EMPLOYEE_FILTERS.items():
		if filters.get(key):
			query = query.where(emp[field] == filters[key])
	return query.run(as_list=1)
