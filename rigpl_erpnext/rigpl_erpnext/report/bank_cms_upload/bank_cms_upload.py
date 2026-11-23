#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt, getdate
from pypika.terms import ValueWrapper

from rigpl_erpnext.utils.report_utils import permitted_names


ENTRY_TYPES = ("Payment Entry", "Employee Advance")
DOCSTATUS = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
DEFAULT_MAX_DAYS = 10
# Only a System Manager can ask for a longer period
USER_MAX_DAYS = 30


def execute(filters=None):
	filters = filters or {}
	if filters.get("entry_type") not in ENTRY_TYPES:
		frappe.throw("Select Payment Entry or Employee Advance", title="Wrong Entry Type")
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	entry_type = filters.get("entry_type")
	# The loans are paid with a Journal Entry (#232)
	doctype = "Journal Entry" if entry_type == "Employee Advance" else entry_type
	cols = [
	"Entry Date:Date:100",
	"Entry#: Link/" + doctype + ":120", "Bank A/C:Link/Bank Account:100",
	{
		"label": "Party Type",
		"fieldname": "party_type",
		"width": 100
	},
	{
		"label": "Party",
		"fieldname": "party",
		"fieldtype": "Dynamic Link",
		"options": "party_type",
		"width": 150
	}, "Company Bank::150", "Name in Bank::300", "Party Bank Account#::150",
	"Party IFSC::100", "Amount:Currency:100"
	]
	if entry_type == "Payment Entry":
		cols += ["Swift Number::100"]
	else:
		cols += ["Existing Loans Pending:Currency:130", "Date of Joining:Date:100",
			{"label": "Employee Advance", "fieldname": "employee_advance", "fieldtype": "Link",
				"options": "Employee Advance", "width": 150}]
	return cols


def get_data(filters):
	check_dates(filters)
	if filters["entry_type"] == "Employee Advance":
		return get_loan_data(filters)
	ba = frappe.qb.DocType("Bank Account")
	doc = frappe.qb.DocType("Payment Entry")
	query = (
		frappe.qb.from_(doc)
		.left_join(ba).on(ba.name == doc.party_bank_account)
		.select(doc.posting_date, doc.name, ba.name, doc.party_type, doc.party, doc.bank_account,
			ba.name_in_bank_records, ba.bank_account_no, ba.branch_code, doc.paid_amount, ba.swift_number)
	)
	if filters.get("payment_type"):
		query = query.where(doc.payment_type == filters["payment_type"])
	query = query.where(doc.posting_date[getdate(filters["from_date"]):getdate(filters["to_date"])]).orderby(doc.name)
	if filters.get("status") in DOCSTATUS:
		query = query.where(doc.docstatus == DOCSTATUS[filters["status"]])
	return query.run(as_list=1)


def get_loan_data(filters):
	"""
	One row per employee debit row of the Journal Entries that pay Employee Advances (#232). The paying account
	is the credit row. Existing Loans Pending is the employee's balance of the advance account on the To Date
	without this row's Employee Advance (its payment and what was deducted from it), and it is blank if not above
	zero. The last column is the Employee Advance of the row. Date of Joining follows the Employee permissions
	of the user.
	"""
	from_date, to_date = getdate(filters["from_date"]), getdate(filters["to_date"])
	entry_filters = {"posting_date": ["between", [from_date, to_date]]}
	if filters.get("status") in DOCSTATUS:
		entry_filters["docstatus"] = DOCSTATUS[filters["status"]]
	names = permitted_names("Journal Entry", entry_filters)
	if not names:
		return []

	je = frappe.qb.DocType("Journal Entry")
	debit = frappe.qb.DocType("Journal Entry Account")
	pay = frappe.qb.DocType("Journal Entry Account").as_("pay")
	ba = frappe.qb.DocType("Bank Account")
	rows = (
		frappe.qb.from_(je)
		.join(debit).on((debit.parent == je.name) & (debit.reference_type == "Employee Advance") & (debit.debit > 0)
			& (debit.party_type == "Employee"))
		.join(pay).on((pay.parent == je.name) & (pay.credit > 0))
		.left_join(ba).on((ba.party_type == "Employee") & (ba.party == debit.party) & (ba.verified == 1))
		.select(je.posting_date, je.name, ba.name, ValueWrapper("Employee"), debit.party, pay.account,
			ba.name_in_bank_records, ba.bank_account_no, ba.branch_code, debit.debit, debit.account, debit.reference_name)
		.where(je.name.isin(list(names))).orderby(je.name)
	).run(as_list=1)
	if not rows:
		return []

	employees, accounts = {row[4] for row in rows}, {row[10] for row in rows}
	balance = get_balances(employees, accounts, to_date)
	own = get_own_amounts({row[11] for row in rows}, employees, accounts, to_date)
	joining = dict(frappe.get_list("Employee", filters={"name": ["in", list(employees)]},
		fields=["name", "date_of_joining"], as_list=True, limit_page_length=0))
	result = []
	for row in rows:
		pending = round(flt(balance.get(row[4])) - flt(own.get(row[11])), 2)
		result.append(row[:10] + [pending if pending > 0 else None, joining.get(row[4]), row[11]])
	return result


def gl_balance_query(accounts, employees):
	gle = frappe.qb.DocType("GL Entry")
	return gle, (
		frappe.qb.from_(gle)
		.where(gle.account.isin(list(accounts)) & (gle.party_type == "Employee") & gle.party.isin(list(employees))
			& (gle.docstatus == 1) & (gle.is_cancelled == 0))
	)


def get_balances(employees, accounts, to_date):
	"""{employee: debit less credit of the advance accounts up to to_date}"""
	gle, query = gl_balance_query(accounts, employees)
	rows = query.where(gle.posting_date <= to_date).select(gle.party, Sum(gle.debit - gle.credit)).groupby(gle.party).run()
	return {party: flt(amount) for party, amount in rows}


def get_own_amounts(advances, employees, accounts, to_date):
	"""{Employee Advance: debit less credit of the advance accounts against it up to to_date}"""
	gle, query = gl_balance_query(accounts, employees)
	rows = (query.where((gle.against_voucher_type == "Employee Advance") & gle.against_voucher.isin(list(advances))
		& (gle.posting_date <= to_date)).select(gle.against_voucher, Sum(gle.debit - gle.credit))
		.groupby(gle.against_voucher)).run()
	return {advance: flt(amount) for advance, amount in rows}


def get_max_days(filters):
	"""Days a bank upload can cover: the Max Days filter, 10 if empty. Above 30 only for a System Manager."""
	max_days = cint(filters.get("max_days")) or DEFAULT_MAX_DAYS
	if max_days < 1:
		frappe.throw("Max Days should be at least 1", title="Wrong Max Days")
	if max_days > USER_MAX_DAYS and "System Manager" not in frappe.get_roles():
		frappe.throw("Only a System Manager can set Max Days above {0}".format(USER_MAX_DAYS), title="Max Days Too Long")
	return max_days


def check_dates(filters):
	"""A bank upload is for at most Max Days."""
	max_days = get_max_days(filters)
	diff = getdate(filters.get("to_date")) - getdate(filters.get("from_date"))
	if diff.days > max_days:
		frappe.throw("Max Difference Between Days allowed is {0}".format(max_days), title="Period Too Long")
	elif diff.days < 0:
		frappe.throw("From Date should be before To Date", title="Wrong Period")
