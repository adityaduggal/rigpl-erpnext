#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt, getdate
from pypika.terms import ValueWrapper

from rigpl_erpnext.utils.report_utils import permitted_names


ENTRY_TYPES = ("Payment Entry", "Employee Advance")
DOCSTATUS = {"Draft": 0, "Submitted": 1, "Cancelled": 2}


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
		cols += ["Existing Loans Pending:Currency:130", "Date of Joining:Date:100"]
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
	without the loan of the row's own entry. Date of Joining follows the Employee permissions of the user.
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
			ba.name_in_bank_records, ba.bank_account_no, ba.branch_code, debit.debit, debit.account)
		.where(je.name.isin(list(names))).orderby(je.name)
	).run(as_list=1)
	if not rows:
		return []

	employees, accounts = {row[4] for row in rows}, {row[10] for row in rows}
	balance = get_balances(employees, accounts, to_date)
	own = get_own_amounts({row[1] for row in rows}, employees, accounts)
	joining = dict(frappe.get_list("Employee", filters={"name": ["in", list(employees)]},
		fields=["name", "date_of_joining"], as_list=True, limit_page_length=0))
	result = []
	for row in rows:
		pending = round(flt(balance.get(row[4])) - flt(own.get((row[1], row[4]))), 2)
		result.append(row[:10] + [pending or None, joining.get(row[4])])
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


def get_own_amounts(vouchers, employees, accounts):
	"""{(Journal Entry, employee): what the entry itself posted to the advance accounts}"""
	gle, query = gl_balance_query(accounts, employees)
	rows = (query.where((gle.voucher_type == "Journal Entry") & gle.voucher_no.isin(list(vouchers)))
		.select(gle.voucher_no, gle.party, Sum(gle.debit - gle.credit)).groupby(gle.voucher_no, gle.party)).run()
	return {(voucher, party): flt(amount) for voucher, party, amount in rows}


def check_dates(filters):
	"""A bank upload is for at most 10 days."""
	diff = getdate(filters.get("to_date")) - getdate(filters.get("from_date"))
	if diff.days > 10:
		frappe.throw("Max Difference Between Days allowed is 10", title="Period Too Long")
	elif diff.days < 0:
		frappe.throw("From Date should be before To Date", title="Wrong Period")
