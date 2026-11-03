# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt, getdate
from pypika.terms import Case
from ....utils.item_attribute_utils import chunks

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
	balances = get_balances(list(emp_map), from_date, to_date)

	data = []
	for emp in sorted(emp_map):
		emp_det = emp_map[emp]
		open_bal, bet_inc, bet_dec = balances.get(emp, (0, 0, 0))
		closing = open_bal + bet_inc - bet_dec
		if filters.get("non_zero") and not (open_bal or bet_inc or bet_dec or closing):
			continue
		data.append([emp, emp_det.employee_name, emp_det.company_registered_with, emp_det.branch,
			emp_det.department, emp_det.designation, emp_det.date_of_joining, emp_det.relieving_date, open_bal,
			bet_inc, bet_dec, closing])
	return columns, data


def get_columns(filters):
	columns = [
		_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140",
		_("Company") + "::50", _("Branch") + "::100", _("Department") + "::100", 
		_("Designation") + "::100", _("Joining Date") + ":Date:80", _("Relieving Date") + ":Date:80",
		_("Opening") + ":Currency:100", _("Period Increase") + ":Currency:100",
		_("Period Decrease") + ":Currency:100", _("Closing") + ":Currency:100"
	]
	return columns

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


def get_balances(employees, from_date, to_date):
	"""
	{employee: (opening, period credit, period debit)} from the Employee GL Entries, in 1 query for
	each chunk of the employees in the report. The opening is credit - debit before from_date.
	"""
	gl = frappe.qb.DocType("GL Entry")
	before = gl.posting_date < from_date
	opening = Sum(Case().when(before, gl.credit - gl.debit).else_(0))
	credit = Sum(Case().when(before, 0).else_(gl.credit))
	debit = Sum(Case().when(before, 0).else_(gl.debit))
	balances = {}
	for chunk in chunks(employees):
		rows = (
			frappe.qb.from_(gl)
			.select(gl.party, opening, credit, debit)
			.where((gl.party_type == "Employee") & gl.party.isin(chunk) & (gl.posting_date <= to_date))
			.groupby(gl.party)
			.run()
		)
		balances.update({party: (flt(o), flt(c), flt(d)) for party, o, c, d in rows})
	return balances
