# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull, Sum
from frappe.utils import cint, flt, nowdate
from pypika.terms import Case
from ....utils.item_attribute_utils import attribute_filters, attribute_sort_key, chunks, get_attribute_map

READY_WAREHOUSES = ("BGH655 - RIGPL", "DEL20A - RIGPL", "Dead Stock - RIGPL")
# Not in WIP1: the ready warehouses and the rejection warehouse
NOT_WIP_WAREHOUSES = READY_WAREHOUSES + ("REJ-DEL20A - RIGPL",)
WIP2_WAREHOUSES = ("BGH655 - RIGPL", "DEL20A - RIGPL")
TEXT = ["Series", "Base Material", "Brand", "{bm} Quality", "Special Treatment", "Tool Type", "Material to Machine",
	"Purpose", "Type Selector"]
NUMERIC = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
FLUTES = "Number of Flutes Zn"
SORT_ORDER = ["Brand", "Special Treatment", "Tool Type", "d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
# filter: attribute
ATTRIBUTE_FILTERS = {"bm": "Base Material", "series": "Series", "tt": "Tool Type", "brand": "Brand",
	"quality": "{bm} Quality", "spl": "Special Treatment"}

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_items(filters)

	return columns, data

def get_columns():
	return [
		"Item:Link/Item:120", 
		
		###Below are attribute fields
		"Series::60", "BM::60", "Brand::40", "Qual::50", "SPL::50", "TT::100",
		"MTM::60", "Purpose::100", "Type::60",
		"D1:Float:50", "W1:Float:50", "L1:Float:60",
		"D2:Float:50", "L2:Float:60", "Zn:Int:30",
		###Above are Attribute fields
		
		"Description::400", "Ready Stock:Int:60", "WIP1:Int:60", "WIP2:Int:60"
	]

def get_items(filters):
	"""
	The items of the filters that have Bins, with their attributes and stock. The attributes come
	from get_attribute_map and the stock from 1 grouped Bin query for each chunk (#131, #187), in
	place of 16 self-joins.
	"""
	bm = filters.get("bm")
	if not bm:
		frappe.throw("Select a Base Material", title="Base Material Needed")
	text = [att.format(bm=bm) for att in TEXT]
	items = get_item_rows(filters, bm)
	stock = get_stock([it.name for it in items])
	items = [it for it in items if it.name in stock]
	att_map = get_attribute_map([it.name for it in items], text + NUMERIC + [FLUTES])
	items.sort(key=lambda it: attribute_sort_key(att_map.get(it.name, {}), SORT_ORDER, set(NUMERIC)))
	data = []
	for it in items:
		values = att_map.get(it.name, {})
		data.append([it.name] + [values.get(att) or "-" for att in text]
			+ [flt(values[att], 3) if values.get(att) is not None else None for att in NUMERIC]
			+ [cint(flt(values[FLUTES])) if values.get(FLUTES) is not None else None, it.description]
			+ list(stock[it.name]))
	return data


def get_item_rows(filters, bm):
	"""The items that are not end of life, have the attribute filters and are not RM."""
	it = frappe.qb.DocType("Item")
	iva = frappe.qb.DocType("Item Variant Attribute")
	is_rm = (
		frappe.qb.from_(iva).select(iva.parent)
		.where((iva.attribute == "Is RM") & iva.attribute_value.isnotnull() & (iva.parenttype == "Item"))
	)
	query = (
		frappe.qb.from_(it)
		.select(it.name, it.description)
		.where(IfNull(it.end_of_life, "2099-12-31") > nowdate())
		.where(it.name.notin(is_rm))
		.where(attribute_filters(it.name, {ATTRIBUTE_FILTERS[key].format(bm=bm): filters.get(key)
			for key in ATTRIBUTE_FILTERS}))
		.orderby(it.name)
	)
	if filters.get("item"):
		query = query.where(it.name == filters["item"])
	return query.run(as_dict=1)


def get_stock(items):
	"""{item: (ready stock, WIP1, WIP2)} of the items that have Bins."""
	bn = frappe.qb.DocType("Bin")
	ready = Sum(Case().when(bn.warehouse.isin(READY_WAREHOUSES), bn.actual_qty).else_(0))
	wip1 = Sum(Case().when(bn.warehouse.notin(NOT_WIP_WAREHOUSES), bn.actual_qty + bn.ordered_qty + bn.planned_qty)
		.else_(0))
	wip2 = Sum(Case().when(bn.warehouse.isin(WIP2_WAREHOUSES), bn.ordered_qty + bn.planned_qty).else_(0))
	stock = {}
	for chunk in chunks(items):
		rows = frappe.qb.from_(bn).select(bn.item_code, ready, wip1, wip2).where(bn.item_code.isin(chunk)) \
			.groupby(bn.item_code).run()
		stock.update({row[0]: row[1:] for row in rows})
	return stock
