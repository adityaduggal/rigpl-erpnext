# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import itertools

import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import flt, nowdate
from ....utils.item_attribute_utils import attribute_filters, attribute_sort_key, chunks, get_attribute_map

TEXT_COLUMNS = ["Base Material", "Brand", "{bm} Quality", "Special Treatment", "Tool Type"]
NUMERIC_COLUMNS = ["d1_mm", "w1_mm", "l1_mm", "Number of Flutes Zn", "d2_mm", "l2_mm", "a1_deg"]
SORT_ORDER = ["Base Material", "Brand", "{bm} Quality", "Tool Type", "d1_mm", "w1_mm", "l1_mm",
	"Number of Flutes Zn", "d2_mm", "l2_mm", "Special Treatment"]
# filter: attribute
ATTRIBUTE_FILTERS = {"bm": "Base Material", "brand": "Brand", "quality": "{bm} Quality",
	"spl": "Special Treatment", "purpose": "Purpose", "type": "Type Selector", "mtm": "Material to Machine",
	"tt": "Tool Type"}


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_item_data(filters)

	return columns, data


def get_columns(filters):
	return [
		{
			"fieldname": "item",
			"label": "Item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120
		},
		{
			"fieldname": "pl1",
			"label": _(filters.pl1),
			"fieldtype": "Currency",
			"width": 70
		},
		{
			"fieldname": "pl1_cur",
			"label": _(filters.pl1) + " Cur",
			"width": 40
		},
		{
			"fieldname": "pl2",
			"label": _(filters.pl2),
			"fieldtype": "Currency",
			"width": 70
		},
		{
			"fieldname": "pl2_cur",
			"label": _(filters.pl2) + " Cur",
			"width": 40
		},
		{
			"fieldname": "pl2_diff",
			"label": _(filters.pl1) + "-" + _(filters.pl2),
			"options": "Float",
			"width": 80
		},
		{
			"fieldname": "pl3",
			"label": _(filters.pl3),
			"fieldtype": "Currency",
			"width": 70
		},
		{
			"fieldname": "pl3_cur",
			"label": _(filters.pl3) + " Cur",
			"width": 40
		},
		{
			"fieldname": "pl3_diff",
			"label": _(filters.pl1) + "-" + _(filters.pl3),
			"options": "Float",
			"width": 80
		},
		{
			"fieldname": "description",
			"label": "Description",
			"width": 400
		},
		{
			"fieldname": "bm",
			"label": "BM",
			"width": 60
		},
		{
			"fieldname": "brand",
			"label": "Brand",
			"width": 60
		},
		{
			"fieldname": "qlt",
			"label": "QLT",
			"width": 80
		},
		{
			"fieldname": "spl",
			"label": "SPL",
			"width": 50
		},
		{
			"fieldname": "tt",
			"label": "TT",
			"width": 150
		},
		{
			"fieldname": "d1",
			"label": "D1",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "w1",
			"label": "W1",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "l1",
			"label": "L1",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "zn",
			"label": "Zn",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "d2",
			"label": "D2",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "l2",
			"label": "L2",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "a1",
			"label": "A1",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "is_pl",
			"label": "Is PL",
			"width": 50
		}
	]


def get_item_data(filters):
	"""
	Items are read with attribute_filters, and their attributes and prices in 1 query for each
	chunk (#131 pattern) in place of 16 self-joins. Each item has 1 row for each combination of its
	prices in the 3 price lists, like the old LEFT JOINs.
	"""
	bm = filters["bm"]
	text, numeric = with_bm(TEXT_COLUMNS, bm), with_bm(NUMERIC_COLUMNS, bm)
	items = get_items(filters, bm)
	att_map = get_attribute_map([it.name for it in items], text + numeric)
	price_lists = [filters.get("pl1"), filters.get("pl2"), filters.get("pl3")]
	prices = get_prices([it.name for it in items], price_lists)
	sort_order, numeric_set = with_bm(SORT_ORDER, bm), set(numeric)
	items.sort(key=lambda it: attribute_sort_key(att_map.get(it.name, {}), sort_order, numeric_set))

	data = []
	for it in items:
		values = att_map.get(it.name, {})
		attribute_cols = [values.get(att) or "-" for att in text]
		numbers = [flt(values[att], 3) if values.get(att) is not None else None for att in numeric]
		options = [prices.get((it.name, pl)) or [frappe._dict()] for pl in price_lists]
		for p1, p2, p3 in itertools.product(*options):
			data.append([it.name, p1.price_list_rate, p1.currency or "-", p2.price_list_rate, p2.currency or "-",
				percent_diff(p1, p2), p3.price_list_rate, p3.currency or "-", percent_diff(p1, p3),
				it.description] + attribute_cols + numbers + ["Yes" if it.pl_item else "No"])
	return data


def with_bm(attributes, bm):
	return [att.format(bm=bm) for att in attributes]


def percent_diff(base, other):
	if not flt(base.price_list_rate) > 0:
		return 0
	if other.price_list_rate is None:
		return None
	return (other.price_list_rate - base.price_list_rate) / base.price_list_rate * 100


def get_items(filters, bm):
	it = frappe.qb.DocType("Item")
	query = (
		frappe.qb.from_(it)
		.select(it.name, it.description, it.pl_item)
		.where(IfNull(it.end_of_life, "2099-12-31") > nowdate())
		.where(attribute_filters(it.name, {ATTRIBUTE_FILTERS[key].format(bm=bm): filters.get(key)
			for key in ATTRIBUTE_FILTERS}))
		.orderby(it.name)
	)
	if filters.get("item"):
		query = query.where(it.name == filters["item"])
	if filters.get("template"):
		query = query.where(it.variant_of == filters["template"])
	if filters.get("is_pl") == 1:
		query = query.where(it.pl_item == 1)
	return query.run(as_dict=1)


def get_prices(items, price_lists):
	"""{(item, price list): [Item Price rows]}"""
	prices = {}
	for chunk in chunks(items):
		for row in frappe.get_all("Item Price", filters={"item_code": ("in", chunk), "price_list": ("in", price_lists)},
				fields=["item_code", "price_list", "price_list_rate", "currency"], order_by="name"):
			prices.setdefault((row.item_code, row.price_list), []).append(row)
	return prices
