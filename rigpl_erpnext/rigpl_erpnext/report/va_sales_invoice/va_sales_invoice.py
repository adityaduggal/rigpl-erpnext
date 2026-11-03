from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from ....utils.item_attribute_utils import get_attribute_map

TEXT = ["Base Material", "Tool Type", "HSS Quality", "Carbide Quality"]
NUMERIC = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_va_entries(filters)

	return columns, data


def get_columns():

	return [
		"Posting Date:Date:80", "Name:Link/Sales Invoice:150" ,"Customer:Link/Customer:250",
		"Item Code:Link/Item:150","Description::350", "Quantity:Float:60",
		"List Price:Float/2:60", "Rate*:Currency:60", "Amount*:Currency:90",
		"Base Metal::100", "Tool Type::100", "HSS Qual::100", "Carb Qual::100",
		"D1 (mm):Float:60", "W1 (mm):Float:60", "L1 (mm):Float:60",
		"D2:Float:60", "L2:Float:60", "Special Treatment::80",
	]


def get_va_entries(filters):
	"""
	The invoice rows come from the posting_date index and the attributes from get_attribute_map
	(#131), in place of 10 self-joins (about 34s for a month).
	"""
	if not filters.get("from_date"):
		frappe.throw("Please Select a From Date first")
	si = frappe.qb.DocType("Sales Invoice")
	sid = frappe.qb.DocType("Sales Invoice Item")
	it = frappe.qb.DocType("Item")
	query = (
		frappe.qb.from_(si)
		.join(sid).on(sid.parent == si.name)
		.join(it).on(it.name == sid.item_code)
		.select(si.posting_date, si.name, si.customer, sid.item_code, sid.description, sid.qty,
			sid.base_price_list_rate, sid.base_rate, sid.base_amount)
		.where((si.docstatus == 1) & (si.posting_date >= filters["from_date"]))
		.orderby(si.posting_date)
		.orderby(si.name)
		.orderby(sid.item_code)
		.orderby(sid.description)
	)
	if filters.get("to_date"):
		query = query.where(si.posting_date <= filters["to_date"])
	rows = query.run(as_list=1)
	att_map = get_attribute_map({row[3] for row in rows}, TEXT + NUMERIC + ["Special Treatment"])
	data = []
	for row in rows:
		values = att_map.get(row[3], {})
		data.append(list(row) + [values.get(att) or "-" for att in TEXT]
			+ [flt(values[att], 3) if values.get(att) is not None else None for att in NUMERIC]
			+ [values.get("Special Treatment") or "-"])
	return data
