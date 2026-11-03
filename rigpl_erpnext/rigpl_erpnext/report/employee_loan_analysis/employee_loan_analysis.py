# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
"""
Loans of Employee Advance RIGPL and their Salary Slip deductions (#199). Summary: one row per employee
with opening, given, deducted and closing balance. Details: the documents of one employee.
"""

import frappe
from frappe.utils import cint, flt

from rigpl_erpnext.utils.report_utils import blank_zeros

LOAN_DOCTYPE = "Employee Advance RIGPL"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if cint(filters.details) and not filters.employee:
		frappe.throw("Please select an Employee for getting Loan Details")
	values = get_values(filters)
	employees = get_employees(filters, values)
	if cint(filters.details) and filters.employee not in employees:
		frappe.throw("Not permitted to read Employee {0}".format(filters.employee), frappe.PermissionError)
	opening = get_opening(values, list(employees))
	given = sum_by_employee(LOAN_SQL + " AND el.posting_date BETWEEN %(from_date)s AND %(to_date)s", values,
		list(employees))
	deducted = sum_by_employee(DEDUCTION_SQL + " AND ss.posting_date BETWEEN %(from_date)s AND %(to_date)s",
		values, list(employees))

	data = []
	for emp in sorted(employees):
		det = employees[emp]
		ob = opening.get(emp, 0)
		cb = ob + given.get(emp, 0) - deducted.get(emp, 0)
		if not cint(filters.details) and (ob > 0 or given.get(emp, 0) > 0 or deducted.get(emp, 0) > 0 or cb > 0):
			data.append([emp, det.employee_name, det.status, det.relieving_date or "2099-12-31", ob,
				given.get(emp, 0), deducted.get(emp, 0), cb])

	if cint(filters.details):
		emp = filters.employee
		det = employees.get(emp, frappe._dict())
		ob = opening.get(emp, 0)
		cb = ob + given.get(emp, 0) - deducted.get(emp, 0)
		data.append([filters.from_date, "", "Opening Balance", ob, 0, "", ""])
		for row in get_details(values):
			data.append([row[0], emp, det.employee_name, row[1], row[2], row[3], row[4]])
		data.append([filters.to_date, "", "Closing Balance", cb, 0, "", ""])
		data.append([filters.to_date, "", "Adjust", -1 * cb, 0, "", ""])

	return get_columns(filters), [blank_zeros(row) for row in data]


LOAN_SQL = f"""SELECT eld.employee, SUM(eld.loan_amount)
	FROM `tab{LOAN_DOCTYPE}` el JOIN `tabEmployee Loan Detail` eld ON eld.parent = el.name
	WHERE el.docstatus = 1 AND eld.employee IN %(employees)s"""
DEDUCTION_SQL = """SELECT ss.employee, SUM(ssd.amount)
	FROM `tabSalary Slip` ss JOIN `tabSalary Detail` ssd ON ssd.parent = ss.name
	WHERE ss.docstatus = 1 AND IFNULL(ssd.employee_loan, '') != '' AND ss.employee IN %(employees)s"""


def get_columns(filters):
	if cint(filters.details):
		return [
			"Posting Date:Date:80", "Employee:Link/Employee:100", "Employee Name::180",
			"Loan Given:Currency:100", "Loan Deducted:Currency:100",
			{"label": "Document", "fieldname": "doc", "width": 120},
			{"label": "Document No", "fieldname": "doc_no", "fieldtype": "Dynamic Link", "options": "doc",
				"width": 150},
		]
	return [
		"Employee:Link/Employee:100", "Employee Name::180", "Status::100",
		"Relieving Date:Date:100", "Opening Balance:Currency:100",
		"Loan Given:Currency:100", "Loan Deducted:Currency:100", "Closing Balance:Currency:100",
	]


def get_values(filters):
	return {key: filters.get(key) for key in ("company", "branch", "department", "employee", "from_date",
		"to_date")}


def get_employees(filters, values):
	"""Employees the user can read (#206). Loans and deductions are then read only for them."""
	emp_filters = {"docstatus": 0}
	for key, field in (("company", "company_registered_with"), ("branch", "branch"),
			("department", "department"), ("employee", "name")):
		if filters.get(key):
			emp_filters[field] = values[key]
	rows = frappe.get_list("Employee", filters=emp_filters, limit_page_length=0,
		fields=["name", "employee_name", "relieving_date", "status"])
	return {row.name: row for row in rows}


def get_opening(values, employees):
	loans = sum_by_employee(LOAN_SQL + " AND el.posting_date < %(from_date)s", values, employees)
	deductions = sum_by_employee(DEDUCTION_SQL + " AND ss.posting_date < %(from_date)s", values, employees)
	return {emp: loans.get(emp, 0) - deductions.get(emp, 0) for emp in set(loans) | set(deductions)}


def sum_by_employee(query, values, employees):
	if not employees:
		return {}
	rows = frappe.db.sql(query + " GROUP BY 1", dict(values, employees=employees))
	return {emp: flt(amount) for emp, amount in rows}


def get_details(values):
	loans = frappe.db.sql(f"""SELECT el.posting_date, eld.loan_amount, 0, %(doctype)s, el.name
		FROM `tab{LOAN_DOCTYPE}` el JOIN `tabEmployee Loan Detail` eld ON eld.parent = el.name
		WHERE el.docstatus = 1 AND eld.employee = %(employee)s
			AND el.posting_date BETWEEN %(from_date)s AND %(to_date)s""",
		dict(values, doctype=LOAN_DOCTYPE), as_list=True)
	deductions = frappe.db.sql("""SELECT ss.posting_date, 0, SUM(ssd.amount), 'Salary Slip', ss.name
		FROM `tabSalary Slip` ss JOIN `tabSalary Detail` ssd ON ssd.parent = ss.name
		WHERE ss.docstatus = 1 AND IFNULL(ssd.employee_loan, '') != '' AND ss.employee = %(employee)s
			AND ss.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY ss.name""", values, as_list=True)
	return sorted(loans + deductions)
