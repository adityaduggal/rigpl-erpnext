#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import getdate


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		"PE#:Link/Payment Entry:120",
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
		}, "Party Name::200", "Company Bank::150", "Party Bank Account#::150", "Party IFSC::100", "Amount:Currency:100",
		"Swift Number::100"
	]


def get_data(filters):
	cond = get_conditions(filters)
	query = """SELECT pe.name, pe.party_type, pe.party, ba.name_in_bank_records, pe.bank_account, ba.bank_account_no, 
	ba.branch_code, pe.paid_amount, ba.swift_number FROM `tabPayment Entry` pe 
		LEFT JOIN `tabBank Account` ba ON ba.name = pe.party_bank_account 
	WHERE pe.docstatus < 3 %s ORDER BY pe.name""" % cond
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
	return cond
