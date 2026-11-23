# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt, getdate
from pypika.terms import Case
from ....utils.item_attribute_utils import chunks
from ....utils.report_utils import blank_zeros

# filter: Employee field
EMPLOYEE_FILTERS = {"employee": "name", "branch": "branch", "department": "department", "designation": "designation",
	"company_registered_with": "company_registered_with"}

def execute(filters=None):
	filters = filters or {}
	from_date, to_date = getdate(filters.get("from_date")), getdate(filters.get("to_date"))
	if from_date > to_date:
		frappe.throw("From Date cannot be after To Date", title="Wrong Period")
	columns = get_columns(filters)
	emp_map = get_employee_details(filters)
	balances = get_balances(list(emp_map), from_date, to_date, filters.get("company"))

	data, left_with_balance = [], []
	for emp in sorted(emp_map):
		emp_det = emp_map[emp]
		open_bal, bet_inc, bet_dec, loans = balances.get(emp, (0, 0, 0, 0))
		closing = open_bal + bet_inc - bet_dec
		# Non-zero rows always show. Zero rows show only when Non Zero is off and the employee was active in the period.
		if not (open_bal or bet_inc or bet_dec or closing):
			joined = not emp_det.date_of_joining or getdate(emp_det.date_of_joining) <= to_date
			if filters.get("non_zero") or not joined or emp_det.relieving_date < from_date:
				continue
		row = blank_zeros([emp, emp_det.employee_name, emp_det.company_registered_with, emp_det.branch,
			emp_det.department, emp_det.designation, emp_det.date_of_joining, emp_det.relieving_date, open_bal,
			bet_inc, bet_dec, closing, loans, closing - loans])
		# Left on or before To Date with a balance: listed first. The desk shows it red (same rule in the .js).
		(left_with_balance if closing and emp_det.relieving_date <= to_date else data).append(row)
	return columns, left_with_balance + data


def get_columns(filters):
	columns = [
		("employee", _("Employee"), "Link", "Employee", 100), ("employee_name", _("Employee Name"), "Data", None, 140),
		("company", _("Company"), "Data", None, 50), ("branch", _("Branch"), "Data", None, 100),
		("department", _("Department"), "Data", None, 100), ("designation", _("Designation"), "Data", None, 100),
		("date_of_joining", _("Joining Date"), "Date", None, 80), ("relieving_date", _("Relieving Date"), "Date", None, 80),
		("opening", _("Opening"), "Currency", None, 100), ("period_increase", _("Period Increase"), "Currency", None, 100),
		("period_decrease", _("Period Decrease"), "Currency", None, 100), ("closing", _("Closing"), "Currency", None, 100),
		("closing_loans", _("Closing Loans/Advances"), "Currency", None, 100),
		("closing_others", _("Closing Others"), "Currency", None, 100),
	]
	return [{"fieldname": name, "label": label, "fieldtype": fieldtype, "options": options, "width": width}
		for name, label, fieldtype, options, width in columns]

def get_employee_details(filters):
	"""Employees the user can read (#206). GL Entries are then read only for them."""
	emp_filters = {"docstatus": 0}
	emp_filters.update({field: filters[key] for key, field in EMPLOYEE_FILTERS.items() if filters.get(key)})
	rows = frappe.get_list("Employee", filters=emp_filters, limit_page_length=0,
		fields=["name", "employee_name", "designation", "department", "branch", "company_registered_with",
			"date_of_joining", "relieving_date"])
	for row in rows:
		row.relieving_date = row.relieving_date or getdate("2099-12-31")
	return {d.name: d for d in rows}


def get_balances(employees, from_date, to_date, company=None):
	"""
	{employee: (opening, period credit, period debit, loans closing)} from the Employee GL Entries, in 1 query
	for each chunk of the employees in the report. The opening is credit - debit before from_date. Loans
	closing is credit - debit up to to_date of the rows against an Employee Advance. Cancelled rows are skipped.
	"""
	gl = frappe.qb.DocType("GL Entry")
	before = gl.posting_date < from_date
	opening = Sum(Case().when(before, gl.credit - gl.debit).else_(0))
	credit = Sum(Case().when(before, 0).else_(gl.credit))
	debit = Sum(Case().when(before, 0).else_(gl.debit))
	loans = Sum(Case().when(gl.against_voucher_type == "Employee Advance", gl.credit - gl.debit).else_(0))
	balances = {}
	for chunk in chunks(employees):
		query = (
			frappe.qb.from_(gl)
			.select(gl.party, opening, credit, debit, loans)
			.where((gl.party_type == "Employee") & gl.party.isin(chunk) & (gl.posting_date <= to_date)
				& (gl.is_cancelled == 0))
			.groupby(gl.party)
		)
		if company:
			query = query.where(gl.company == company)
		balances.update({party: (flt(o), flt(c), flt(d), flt(n)) for party, o, c, d, n in query.run()})
	return balances
