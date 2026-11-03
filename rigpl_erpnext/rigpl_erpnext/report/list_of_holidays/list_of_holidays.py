# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_entries(filters)

	return columns, data

def get_columns(filters):
	return [
		"Name:Link/Holiday List:150", "Date:Date:100", "Day::100", 
		"Holiday Name::200", "Weekly Off::50", "Base Holiday List:Link/Holiday List:150"
		]

def get_entries(filters):
	"""The holidays of all the holiday lists made from the base list `name`, in 1 query."""
	if not filters.get("name"):
		frappe.throw("Select a base Holiday List", title="Holiday List Needed")
	hld = frappe.qb.DocType("Holiday List")
	hol = frappe.qb.DocType("Holiday")
	query = (
		frappe.qb.from_(hld)
		.join(hol).on(hol.parent == hld.name)
		.select(hld.name, hol.holiday_date, hol.description, hld.weekly_off, hld.base_holiday_list)
		.where(hld.base_holiday_list == filters["name"])
		.orderby(hld.name)
		.orderby(hol.holiday_date)
	)
	if filters.get("from_date"):
		query = query.where(hol.holiday_date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(hol.holiday_date <= filters["to_date"])
	return [[d.name, d.holiday_date, d.holiday_date.strftime("%A"), d.description,
		is_weekly_off(d.description, d.weekly_off), d.base_holiday_list] for d in query.run(as_dict=1)]


def is_weekly_off(description, weekly_off):
	"""Yes when the holiday is the weekly off. Like the old SQL: no case, and an empty value is No."""
	return "Yes" if description and weekly_off and description.casefold() == weekly_off.casefold() else "No"
