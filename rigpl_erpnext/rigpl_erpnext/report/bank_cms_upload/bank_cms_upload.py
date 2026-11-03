#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import getdate
from pypika.terms import ValueWrapper


ENTRY_TYPES = ("Payment Entry", "Employee Advance RIGPL")
DOCSTATUS = {"Draft": 0, "Submitted": 1, "Cancelled": 2}


def execute(filters=None):
	filters = filters or {}
	if filters.get("entry_type") not in ENTRY_TYPES:
		frappe.throw("Select Payment Entry or Employee Advance RIGPL", title="Wrong Entry Type")
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	entry_type = filters.get("entry_type")
	cols = [
	"Entry Date:Date:100",
	"Entry#: Link/" + entry_type + ":120", "Bank A/C:Link/Bank Account:100",
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
	return cols


def get_data(filters):
	check_dates(filters)
	ba = frappe.qb.DocType("Bank Account")
	if filters["entry_type"] == "Payment Entry":
		doc = frappe.qb.DocType("Payment Entry")
		query = (
			frappe.qb.from_(doc)
			.left_join(ba).on(ba.name == doc.party_bank_account)
			.select(doc.posting_date, doc.name, ba.name, doc.party_type, doc.party, doc.bank_account,
				ba.name_in_bank_records, ba.bank_account_no, ba.branch_code, doc.paid_amount, ba.swift_number)
		)
		if filters.get("payment_type"):
			query = query.where(doc.payment_type == filters["payment_type"])
	else:
		doc = frappe.qb.DocType("Employee Advance RIGPL")
		eld = frappe.qb.DocType("Employee Loan Detail")
		query = (
			frappe.qb.from_(doc)
			.join(eld).on((eld.parent == doc.name) & (eld.parenttype == "Employee Advance RIGPL"))
			.left_join(ba).on((ba.party_type == "Employee") & (ba.party == eld.employee) & (ba.verified == 1))
			.select(doc.posting_date, doc.name, ba.name, ValueWrapper("Employee"), eld.employee, doc.credit_account,
				ba.name_in_bank_records, ba.bank_account_no, ba.branch_code, eld.loan_amount)
		)
	query = query.where(doc.posting_date[getdate(filters["from_date"]):getdate(filters["to_date"])]).orderby(doc.name)
	if filters.get("status") in DOCSTATUS:
		query = query.where(doc.docstatus == DOCSTATUS[filters["status"]])
	return query.run(as_list=1)


def check_dates(filters):
	"""A bank upload is for at most 10 days."""
	diff = getdate(filters.get("to_date")) - getdate(filters.get("from_date"))
	if diff.days > 10:
		frappe.throw("Max Difference Between Days allowed is 10", title="Period Too Long")
	elif diff.days < 0:
		frappe.throw("From Date should be before To Date", title="Wrong Period")
