#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import flt
from ....utils.item_attribute_utils import attribute_filters, attribute_sort_key, get_attribute_map
from ....utils.report_utils import blank_zeros

TEXT = ["Base Material", "{bm} Quality", "Tool Type"]
NUMERIC = ["d1_mm", "w1_mm"]
SORT_ORDER = ["Base Material", "Tool Type", "{bm} Quality", "d1_mm", "w1_mm"]
# filter: attribute
ATTRIBUTE_FILTERS = {"bm": "Base Material", "tt": "Tool Type", "qa": "{bm} Quality"}


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	return[
		"Indent#:Link/Material Request:100", "Date:Date:80", "Schedule Date:Date:80", "Item Code:Link/Item:140",
		"Description::250", "Qty:Float:80", "UoM::20", "Ordered:Float:80", "BM::50",
		"Material Grade::80", "Type of Tool::150", "D1:Float:50", "W1:Float:50"
	]


def get_data(filters):
	"""
	The pending indent rows of the filters, with the attributes from get_attribute_map in place
	of 5 self-joins (#187).
	"""
	bm = filters.get("bm")
	if not bm:
		frappe.throw("Select a Base Material", title="Base Material Needed")
	text = [att.format(bm=bm) for att in TEXT]
	rows = get_indent_rows(filters, bm)
	att_map = get_attribute_map({row.item_code for row in rows}, text + NUMERIC)
	sort_order = [att.format(bm=bm) for att in SORT_ORDER]
	rows.sort(key=lambda row: attribute_sort_key(att_map.get(row.item_code, {}), sort_order, set(NUMERIC)))
	data = []
	for row in rows:
		values = att_map.get(row.item_code, {})
		data.append(blank_zeros([row.name, row.transaction_date, row.schedule_date, row.item_code, row.description,
			row.qty, row.uom, row.ordered_qty] + [values.get(att) or "-" for att in text]
			+ [flt(values[att], 3) if values.get(att) is not None else None for att in NUMERIC]))
	return data


def get_indent_rows(filters, bm):
	"""The submitted indent rows that are not stopped and not fully ordered."""
	mr = frappe.qb.DocType("Material Request")
	mri = frappe.qb.DocType("Material Request Item")
	query = (
		frappe.qb.from_(mr).join(mri).on(mri.parent == mr.name)
		.select(mr.name, mr.transaction_date, mri.schedule_date, mri.item_code, mri.description, mri.qty, mri.uom,
			mri.ordered_qty)
		.where((mr.docstatus == 1) & (mr.status != "Stopped"))
		.where(IfNull(mri.ordered_qty, 0) < IfNull(mri.qty, 0))
		.where(attribute_filters(mri.item_code, {ATTRIBUTE_FILTERS[key].format(bm=bm): filters.get(key)
			for key in ATTRIBUTE_FILTERS}))
		.orderby(mr.transaction_date).orderby(mr.name).orderby(mri.idx)
	)
	if filters.get("date"):
		query = query.where(mr.transaction_date <= filters["date"])
	return query.run(as_dict=1)
