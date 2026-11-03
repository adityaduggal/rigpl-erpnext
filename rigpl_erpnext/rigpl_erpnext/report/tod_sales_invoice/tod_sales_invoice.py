from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from ....utils.item_attribute_utils import chunks


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_si_entries(filters)

	return columns, data


def get_columns(filters):
	if filters.get("summary"):
		if filters.get("separated_tod"):
			return ["Customer:Link/Customer:200","Net Total:Currency:120", "TOD Applicable::60"]
		else:
			return ["Customer:Link/Customer:200","Net Total:Currency:120"]
	else:
		return ["Invoice#:Link/Sales Invoice:120", "Date:Date:80", "Customer:Link/Customer:200",
		"Item Code:Link/Item:150", "Description::200", "Qty:Float:80",
		"List Price:Currency:80", "Discount:Float:40",
		"Net Price:Currency:120", "Net Total:Currency:120", "TOD App::60", "PL Item::60"]


def yes_no(value):
	return "Yes" if value else "No"


def get_si_entries(filters):
	"""
	The invoice rows come from the posting_date index and the Item flags from 1 query per chunk.
	A join to Item made MariaDB read all Items first (about 27s for a year).
	"""
	rows = get_invoice_rows(filters)
	items = get_item_flags(row.item_code for row in rows)
	rows = [row for row in rows if row.item_code in items]
	if not filters.get("summary"):
		return [[row.name, row.posting_date, row.customer, row.item_code, row.description, row.qty,
			row.base_price_list_rate, row.discount_percentage, row.base_net_rate, row.base_net_amount,
			yes_no(items[row.item_code].stock_maintained), yes_no(items[row.item_code].pl_item)] for row in rows]
	totals = {}
	for row in rows:
		key = (row.customer, yes_no(items[row.item_code].stock_maintained)) if filters.get("separated_tod") \
			else (row.customer,)
		totals[key] = totals.get(key, 0) + flt(row.base_net_amount)
	ordered = sorted(totals.items(), key=lambda kv: (kv[0][0].casefold(),) + kv[0][1:])
	return [[key[0], total] + list(key[1:]) for key, total in ordered]


def get_invoice_rows(filters):
	si = frappe.qb.DocType("Sales Invoice")
	sid = frappe.qb.DocType("Sales Invoice Item")
	query = (
		frappe.qb.from_(si)
		.join(sid).on(sid.parent == si.name)
		.select(si.name, si.posting_date, si.customer, sid.item_code, sid.description, sid.qty,
			sid.base_price_list_rate, sid.discount_percentage, sid.base_net_rate, sid.base_net_amount)
		.where(si.docstatus == 1)
		.orderby(si.customer)
		.orderby(si.posting_date)
		.orderby(si.name)
		.orderby(sid.item_code)
	)
	if filters.get("fiscal_year"):
		start, end = frappe.db.get_value("Fiscal Year", filters["fiscal_year"], ["year_start_date", "year_end_date"])
		query = query.where(si.posting_date[start:end])
	if filters.get("from_date"):
		query = query.where(si.posting_date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(si.posting_date <= filters["to_date"])
	for field in ("customer", "letter_head"):
		if filters.get(field):
			query = query.where(si[field] == filters[field])
	return query.run(as_dict=1)


def get_item_flags(item_codes):
	items = {}
	for chunk in chunks(item_codes):
		for item in frappe.get_all("Item", filters={"name": ("in", chunk)}, fields=["name", "stock_maintained", "pl_item"]):
			items[item.name] = item
	return items
