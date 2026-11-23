# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
"""
Loans (Employee Advance with repay_unclaimed_amount_from_salary = 1) read from the GL (#233). Both the Journal
Entry that gives a loan and the Salary Slip that deducts it set against_voucher to the Employee Advance.
Summary: one row per employee with opening, given, deducted and closing balance. Details: the GL rows of one
employee with a running balance. Each view runs a fixed number of queries.
"""

import frappe
from frappe.query_builder.functions import Min, Sum
from frappe.utils import flt, getdate
from pypika.terms import Case

from rigpl_erpnext.utils.report_utils import blank_zeros, employees_with_left

# Values of the "Show" filter (also in the .js file)
EXISTING = "Employees with Existing Loans (Active Balances)"
TRANSACTIONS = "Employees with Transactions in Period"
DETAILS = "Details of 1 Employee"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.view == DETAILS and not filters.employee:
		frappe.throw("Please select an Employee for getting Loan Details")
	employees, only_left = get_employees(filters)
	if filters.view == DETAILS:
		if filters.employee not in employees:
			frappe.throw("Not permitted to read Employee {0}".format(filters.employee), frappe.PermissionError)
		data = get_details(filters, employees[filters.employee])
	else:
		data = get_summary(filters, employees, only_left)
	return get_columns(filters), [blank_zeros(row) for row in data]


def get_columns(filters):
	if filters.view == DETAILS:
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
		("deducted", "Loan Deducted", "Currency", None, 100), ("closing", "Closing Balance", "Currency", None, 100),
		("pending_advances", "Pending Advances", "Data", None, 220)]
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
	"""
	{employee: (opening, given, deducted, pending advances)} in 1 query. A GL row before the From Date is opening.
	Deductions repay the oldest loan first, so the Closing balance is allocated to the newest advances: an advance
	is pending while the amount given in the newer ones is less than the Closing balance. The names are sorted.
	"""
	query, gl = loan_gl("party", "against_voucher", employee=employee)
	before, period = gl.posting_date < filters.from_date, gl.posting_date >= filters.from_date
	query = (query.select(Sum(Case().when(before, gl.debit - gl.credit).else_(0)),
			Sum(Case().when(period, gl.debit).else_(0)), Sum(Case().when(period, gl.credit).else_(0)),
			Sum(gl.debit), Min(gl.posting_date))
		.where(gl.posting_date <= filters.to_date).groupby(gl.party, gl.against_voucher))
	balances, advances = {}, {}
	for party, advance, opening, given, deducted, debit, given_on in query.run():
		totals = balances.setdefault(party, [0, 0, 0])
		totals[0] += flt(opening)
		totals[1] += flt(given)
		totals[2] += flt(deducted)
		advances.setdefault(party, []).append((given_on, advance, flt(debit)))
	return {party: (opening, given, deducted, get_pending(opening + given - deducted, advances[party]))
		for party, (opening, given, deducted) in balances.items()}


def get_pending(closing, advances):
	"""Names of the newest advances, (given on, name, amount given), that the Closing balance still covers"""
	pending = []
	for given_on, name, amount in sorted(advances, reverse=True):
		if flt(closing, 2) <= 0:
			break
		if amount <= 0:
			continue
		pending.append(name)
		closing -= amount
	return sorted(pending)


def get_summary(filters, employees, only_left):
	"""
	One row per employee. Existing Loans lists the employees with a Closing balance, Transactions in Period the
	employees with a loan given or deducted in the period. Employees who left on or before To Date with a Closing
	balance come first (red in the .js file). The employees that only the left rule adds show only with a Closing balance.
	"""
	balances = get_balances(filters)
	to_date = getdate(filters.to_date)
	left, data = [], []
	for emp in sorted(employees):
		opening, given, deducted, pending = balances.get(emp, (0, 0, 0, []))
		closing = opening + given - deducted
		if emp in only_left and not closing:
			continue
		if (given or deducted) if filters.view == TRANSACTIONS else closing:
			det = employees[emp]
			row = [emp, det.employee_name, det.status, det.relieving_date or "2099-12-31", opening, given,
				deducted, closing, ", ".join(pending)]
			(left if closing and det.relieving_date and getdate(det.relieving_date) <= to_date else data).append(row)
	data = left + data
	if data:
		data.append(["Total", "", "", "", *[sum(row[col] for row in data) for col in range(4, 8)], ""])
	return data


def get_details(filters, employee):
	"""Opening balance, the GL rows of the period with a running balance, and the closing balance"""
	opening, given, deducted, _pending = get_balances(filters, employee.name).get(employee.name, (0, 0, 0, []))
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
