# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

PARTY = {"Sales Invoice": "Customer", "Purchase Invoice": "Supplier"}


def execute(filters=None):
	filters = filters or {}
	if filters.get("doctype") not in PARTY:
		frappe.throw("Select Sales Invoice or Purchase Invoice")
	for_name = PARTY[filters["doctype"]]

	columns = get_columns(filters, for_name)
	data = get_data(filters, for_name)
	return columns, data


def get_columns(filters, for_name):
	return [
		filters["doctype"] + "#:Link/" + filters["doctype"] + ":130",
		"Date:Date:80", for_name + ":Link/" + for_name + ":200",
		"Outstanding:Currency:100", "Forex Amt:Currency:100", "Base Amt:Currency:100",
		"Currency::50"
	]


def get_data(filters, for_name):
	def_currency = frappe.get_value("Company", filters.get("company"), "default_currency")
	dt = frappe.qb.DocType(filters["doctype"])
	query = (
		frappe.qb.from_(dt)
		.select(dt.name, dt.posting_date, dt[for_name.lower()], dt.outstanding_amount, dt.grand_total,
			dt.base_grand_total, dt.currency)
		.where((dt.docstatus != 2) & (dt.currency != def_currency))
		.orderby(dt.posting_date, order=frappe.qb.desc)
		.orderby(dt.name, order=frappe.qb.desc)
	)
	if filters.get("from_date"):
		query = query.where(dt.posting_date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(dt.posting_date <= filters["to_date"])
	return query.run(as_list=1)
