# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if filters.get("doctype") == "Sales Invoice":
		for_name = "Customer"
	else:
		for_name = "Supplier"

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
	conditions = get_conditions(filters)
	def_currency = frappe.get_value("Company", filters.get("company"), "default_currency")
	query = """SELECT dt.name, dt.posting_date, dt.%s, dt.outstanding_amount,
		dt.grand_total, dt.base_grand_total, dt.currency
		FROM `tab%s` dt
		WHERE docstatus !=2 AND currency != '%s' %s
		ORDER BY dt.posting_date DESC, dt.name DESC"""%(for_name, filters["doctype"], def_currency, conditions)
	data = frappe.db.sql(query, as_list=1)
	return data

def get_conditions(filters):
	conditions = ""

	if filters.get("from_date"):
		conditions += " AND dt.posting_date >= '%s'" % filters.get("from_date")
	if filters.get("to_date"):
		conditions += " AND dt.posting_date <= '%s'" % filters.get("to_date")

	return conditions