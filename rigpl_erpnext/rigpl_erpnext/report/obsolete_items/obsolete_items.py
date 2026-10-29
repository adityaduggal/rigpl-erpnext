# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import Count, IfNull
from frappe.utils import cint, nowdate
from ....utils.item_attribute_utils import attribute_filters, chunks
from ....utils.report_utils import blank_zeros

ATTRIBUTE_FILTERS = {
	"bm": "Base Material",
	"is_rm": "Is RM",
	"brand": "Brand",
	"spl": "Special Treatment",
	"tt": "Tool Type",
}
# Count column: (DocType, item field). Cancelled Stock Ledger rows are not counted.
COUNT_TABLES = [
	("Sales Order Item", "item_code"),
	("Sales Invoice Item", "item_code"),
	("Purchase Order Item", "item_code"),
	("Purchase Invoice Item", "item_code"),
	("Stock Ledger Entry", "item_code"),
	("Stock Entry Detail", "item_code"),
	("Stock Reconciliation Item", "item_code"),
	("Work Order", "production_item"),
]
MAX_ITEMS = 500


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_items(filters)

	return columns, data

def get_columns():
	return [
		"Item:Link/Item:100", "Description::300", "PL::35",
		"SO::35", "PO::35","Web::35", "TOD::35",
		"#SO:Int:40", "#SI:Int:40", "#PO:Int:40", "#PI:Int:40",
		"#SLE:Int:40", "#STE:Int:40", "#SR:Int:40", "#PRD:Int:40",
		"VR:Currency:100",
		"Created By:Link/User:150", "Creation:Date:130"
	]

def get_items(filters):
	items = get_item_list(filters)
	if len(items) > MAX_ITEMS:
		frappe.throw(("Server overload possible due to {0} rows of data, kindly reduce \
			the lines by selecting filters").format(len(items)))

	names = [d.name for d in items]
	counts = get_counts(names)
	published = get_published(names)
	data = []
	for it in items:
		row = [it.name, it.description, "Yes" if it.pl_item else "No", it.is_sales_item,
			it.is_purchase_item, published.get(it.name, 0), "Yes" if it.stock_maintained else "No"]
		row += [counts[table].get(it.name, 0) for table, _ in COUNT_TABLES]
		row += [it.valuation_rate, it.owner or "Administrator", it.creation]
		data.append(blank_zeros(row))
	return data

def get_item_list(filters):
	it = frappe.qb.DocType("Item")
	query = (
		frappe.qb.from_(it)
		.select(it.name, it.description, it.pl_item, it.is_sales_item, it.is_purchase_item,
			it.stock_maintained, it.valuation_rate, it.owner, it.creation)
		.where(IfNull(it.end_of_life, "2099-12-31") > (filters.get("eol") or nowdate()))
		.where(it.pl_item == cint(filters.get("is_pl_item")))
		.where(it.has_variants == cint(filters.get("has_variants")))
		.where(attribute_filters(it.name, {att: filters.get(key) for key, att in ATTRIBUTE_FILTERS.items()}))
		.orderby(it.name)
	)
	if filters.get("item"):
		query = query.where(it.name == filters["item"])
	if filters.get("quality"):
		# The quality attribute depends on the Base Material, so any "... Quality" attribute matches
		iva = frappe.qb.DocType("Item Variant Attribute")
		query = query.where(it.name.isin(
			frappe.qb.from_(iva).select(iva.parent)
			.where(iva.attribute.like("%Quality") & (iva.attribute_value == filters["quality"]))
		))
	return query.run(as_dict=True)

def get_counts(items):
	"""Return {DocType: {item: row count}}, one grouped query per DocType per chunk."""
	counts = {table: {} for table, _ in COUNT_TABLES}
	for chunk in chunks(items):
		for table, field in COUNT_TABLES:
			doc = frappe.qb.DocType(table)
			query = (
				frappe.qb.from_(doc)
				.select(doc[field], Count(doc.name))
				.where(doc[field].isin(chunk))
				.groupby(doc[field])
			)
			if table == "Stock Ledger Entry":
				query = query.where(doc.is_cancelled == 0)
			counts[table].update(dict(query.run()))
	return counts

def get_published(items):
	"""Return {item: published} of the Website Item of each item."""
	published = {}
	for chunk in chunks(items):
		for item, value in frappe.get_all("Website Item", filters={"item_code": ("in", chunk)},
				fields=["item_code", "published"], as_list=1):
			published.setdefault(item, value)
	return published
