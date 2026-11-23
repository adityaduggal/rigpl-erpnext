# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
"""
Loans (Employee Advance with repay_unclaimed_amount_from_salary = 1) read from the GL (#233). Both the Journal
Entry that gives a loan and the Salary Slip that deducts it set against_voucher to the Employee Advance.
Summary: one row per employee with opening, given, deducted and closing balance. Details: the GL rows of one
employee with a running balance. Each view runs a fixed number of queries.
"""

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt, getdate
from pypika.terms import Case

from rigpl_erpnext.utils.report_utils import blank_zeros, employees_with_left


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if cint(filters.details) and not filters.employee:
		frappe.throw("Please select an Employee for getting Loan Details")
	employees, only_left = get_employees(filters)
	if cint(filters.details):
		if filters.employee not in employees:
			frappe.throw("Not permitted to read Employee {0}".format(filters.employee), frappe.PermissionError)
		data = get_details(filters, employees[filters.employee])
	else:
		data = get_summary(filters, employees, only_left)
	return get_columns(filters), [blank_zeros(row) for row in data]


def get_columns(filters):
	if cint(filters.details):
		return [
			"Posting Date:Date:80", "Employee:Link/Employee:100", "Employee Name::180",
			"Loan Given:Currency:100", "Loan Deducted:Currency:100", "Balance:Currency:100",
			{"label": "Document", "fieldname": "doc", "width": 120},
			{"label": "Document No", "fieldname": "doc_no", "fieldtype": "Dynamic Link", "options": "doc",
				"width": 150},
		]
	columns = [("employee", "Employee", "Link", "Employee", 100), ("employee_name", "Employee Name", "Data", None, 180),
		("status", "Status", "Data", None, 100), ("relieving_date", "Relieving Date", "Date", None, 100),
		("opening", "Opening Balance", "Currency", None, 100), ("given", "Loan Given", "Currency", None, 100),
		("deducted", "Loan Deducted", "Currency", None, 100), ("closing", "Closing Balance", "Currency", None, 100)]
	return [{"fieldname": name, "label": label, "fieldtype": fieldtype, "options": options, "width": width}
		for name, label, fieldtype, options, width in columns]


def get_employees(filters):
	"""Employees the user can read (#206) and the employees who left on or before To Date (a restricted user
	must see their loans too). Returns the rows and the names that only the left rule adds."""
	emp_filters = {"docstatus": 0}
	for key, field in (("company", "company_registered_with"), ("branch", "branch"),
			("department", "department"), ("employee", "name")):
		if filters.get(key):
			emp_filters[field] = filters.get(key)
	return employees_with_left(emp_filters, ["name", "employee_name", "relieving_date", "status"],
		filters.to_date)


def loan_gl(*fields, employee=None):
	"""Query of the GL rows of submitted loans (the caller adds the dates). Returns the query and the GL table."""
	gl, advance = frappe.qb.DocType("GL Entry"), frappe.qb.DocType("Employee Advance")
	query = (frappe.qb.from_(gl).join(advance).on(advance.name == gl.against_voucher)
		.select(*[getattr(gl, field) for field in fields])
		.where((gl.against_voucher_type == "Employee Advance") & (gl.is_cancelled == 0)
			& (gl.party_type == "Employee") & (advance.docstatus == 1)
			& (advance.repay_unclaimed_amount_from_salary == 1)))
	if employee:
		query = query.where(gl.party == employee)
	return query, gl


def get_balances(filters, employee=None):
	"""{employee: (opening, given, deducted)} in 1 query. A GL row before the From Date is opening."""
	query, gl = loan_gl("party", employee=employee)
	before, period = gl.posting_date < filters.from_date, gl.posting_date >= filters.from_date
	query = (query.select(Sum(Case().when(before, gl.debit - gl.credit).else_(0)),
			Sum(Case().when(period, gl.debit).else_(0)), Sum(Case().when(period, gl.credit).else_(0)))
		.where(gl.posting_date <= filters.to_date).groupby(gl.party))
	return {party: (flt(opening), flt(given), flt(deducted)) for party, opening, given, deducted in
		query.run()}


def get_summary(filters, employees, only_left):
	"""Employees who left on or before To Date with a Closing balance come first (red in the .js file)"""
	balances = get_balances(filters)
	to_date = getdate(filters.to_date)
	left, data = [], []
	for emp in sorted(employees):
		opening, given, deducted = balances.get(emp, (0, 0, 0))
		closing = opening + given - deducted
		if emp in only_left and not closing:
			continue
		if opening > 0 or given > 0 or deducted > 0 or closing > 0 or emp in only_left:
			det = employees[emp]
			row = [emp, det.employee_name, det.status, det.relieving_date or "2099-12-31", opening, given,
				deducted, closing]
			(left if closing and det.relieving_date and getdate(det.relieving_date) <= to_date else data).append(row)
	data = left + data
	if data:
		data.append(["Total", "", "", "", *[sum(row[col] for row in data) for col in range(4, 8)]])
	return data


def get_details(filters, employee):
	"""Opening balance, the GL rows of the period with a running balance, and the closing balance"""
	opening, given, deducted = get_balances(filters, employee.name).get(employee.name, (0, 0, 0))
	query, gl = loan_gl("posting_date", "debit", "credit", "voucher_type", "voucher_no", employee=employee.name)
	rows = (query.where(gl.posting_date.between(filters.from_date, filters.to_date))
		.orderby(gl.posting_date).orderby(gl.creation).run())
	balance = opening
	data = [[filters.from_date, "", "Opening Balance", "", "", opening, "", ""]]
	for posting_date, debit, credit, voucher_type, voucher_no in rows:
		balance += flt(debit) - flt(credit)
		data.append([posting_date, employee.name, employee.employee_name, flt(debit), flt(credit), balance,
			voucher_type, voucher_no])
	data.append([filters.to_date, "", "Closing Balance", given, deducted, opening + given - deducted, "", ""])
	return data
