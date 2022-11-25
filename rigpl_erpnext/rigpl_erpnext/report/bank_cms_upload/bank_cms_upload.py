#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import getdate


def execute(filters=None):
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
	cond = get_conditions(filters)
	if filters.get("entry_type") == "Payment Entry":
		query = """SELECT pe.posting_date, pe.name, ba.name, pe.party_type, pe.party, pe.bank_account,
		ba.name_in_bank_records, ba.bank_account_no, ba.branch_code, pe.paid_amount, ba.swift_number
		FROM `tabPayment Entry` pe
			LEFT JOIN `tabBank Account` ba ON ba.name = pe.party_bank_account
		WHERE pe.docstatus < 3 %s ORDER BY pe.name""" % cond
	else:
		query = """SELECT ea.posting_date, ea.name, ba.name, "Employee", eld.employee, ea.credit_account,
		ba.name_in_bank_records, ba.bank_account_no, ba.branch_code, eld.loan_amount
		FROM `tabEmployee Advance` ea, `tabEmployee Loan Detail` eld
			LEFT JOIN `tabBank Account` ba ON ba.party_type = "Employee" AND ba.party = eld.employee AND ba.verified = 1
		WHERE eld.parent = ea.name AND eld.parenttype = "Employee Advance" AND ea.docstatus < 3 %s
		ORDER BY ea.name""" % cond
	data = frappe.db.sql(query, as_list=1)

	return data


def get_conditions(filters):
	cond = ""
	# Difference of Dates cannot be more than 10 days
	diff = getdate(filters.get("to_date")) - getdate(filters.get("from_date"))
	if diff.days > 10:
		frappe.throw("Max Difference Between Days allowed is 10")
	elif diff.days < 0:
		frappe.throw("From Date should be before To Date")

	if filters.get("entry_type") == "Payment Entry":
		if filters.get("payment_type"):
			cond += " AND pe.payment_type = '%s'" % filters.get("payment_type")
		if filters.get("from_date"):
			cond += " AND pe.posting_date >= '%s'" % filters.get("from_date")
		if filters.get("to_date"):
			cond += " AND pe.posting_date <= '%s'" % filters.get("to_date")
		if filters.get("status") == "Draft":
			cond += " AND pe.docstatus = 0"
		elif filters.get("status") == "Submitted":
			cond += " AND pe.docstatus = 1"
		elif filters.get("status") == "Cancelled":
			cond += " AND pe.docstatus = 2"
	else:
		if filters.get("from_date"):
			cond += " AND ea.posting_date >= '%s'" % filters.get("from_date")
		if filters.get("to_date"):
			cond += " AND ea.posting_date <= '%s'" % filters.get("to_date")
		if filters.get("status") == "Draft":
			cond += " AND ea.docstatus = 0"
		elif filters.get("status") == "Submitted":
			cond += " AND ea.docstatus = 1"
		elif filters.get("status") == "Cancelled":
			cond += " AND ea.docstatus = 2"
	return cond
