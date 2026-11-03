# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import itertools

import frappe
from frappe.query_builder.functions import Count, IfNull, Max
from ....utils.item_attribute_utils import chunks

COLUMN_ATTRIBUTES = ["Is RM", "Base Material", "Brand", "{bm} Quality", "Special Treatment", "Tool Type",
	"Material to Machine", "Purpose"]
CETSH = "CETSH Number"
# filter: restriction attribute
RESTRICTION_FILTERS = {"rm": "Is RM", "bm": "Base Material", "brand": "Brand", "quality": "{bm} Quality",
	"spl": "Special Treatment", "purpose": "Purpose", "type": "Type Selector", "mtm": "Material to Machine",
	"tt": "Tool Type"}

def execute(filters=None):
	if not filters: filters = {}
	columns = get_columns()
	data = get_items(filters)
	
	return columns, data
	
def get_columns():
	return[
		"Item:Link/Item:300", "# Variants:Int:50", "Limit:Int:50", "Is RM::50",
		"BM::60", "Brand::60", "Quality::60", "SPL::60", "TT::150", "MTM::60",
		"Purpose::60", "Item Group::200", "WH::150", "Valuation::60",
		"Tolerance:Int:40", "PUR:Int:40", "SALE:Int:40", "WEB:Int:40", "Web Variants:Int:40","PL::40",
		"PRD:Int:40", "CETSH::100", "D1_MM::50", "W1_MM::50", "L1_MM::50",
		"Image::200"
	]

def get_items(filters):
	"""
	The templates with the restriction filters. The restriction values, variant counts and Website
	Item counts come from grouped queries, in place of 10 self-joins and 3 subqueries for each
	template. A template with 2 rows of 1 attribute gets 1 row for each value, like the old joins.
	"""
	bm = filters.get("bm")
	if not bm:
		frappe.throw("Select a Base Material", title="Base Material Needed")
	attributes = [att.format(bm=bm) for att in COLUMN_ATTRIBUTES]
	templates = get_templates(filters, bm)
	names = [it.name for it in templates]
	restrictions = get_restriction_values(names, attributes + [CETSH])
	variants, web_variants, published = get_counts(names)
	data = []
	for it in templates:
		values = restrictions.get(it.name, {})
		for combo in itertools.product(*[values.get(att) or ["-"] for att in attributes + [CETSH]]):
			data.append([it.name, variants.get(it.name, 0), it.variant_limit] + list(combo[:-1])
				+ [it.item_group, it.default_warehouse, it.valuation_method, it.tolerance, it.is_purchase_item,
				it.is_sales_item, published.get(it.name, 0), web_variants.get(it.name, 0),
				"Yes" if it.pl_item else "No", it.is_pro_applicable, combo[-1], None, None, None, "-" if it.image is None else it.image])
	return data


def get_templates(filters, bm):
	it = frappe.qb.DocType("Item")
	ivr = frappe.qb.DocType("Item Variant Restrictions")
	query = (
		frappe.qb.from_(it)
		.select(it.name, it.variant_limit, it.item_group, it.default_warehouse, it.valuation_method, it.tolerance,
			it.is_purchase_item, it.is_sales_item, it.pl_item, it.is_pro_applicable, it.image)
		.where(it.has_variants == 1)
		.orderby(it.name)
	)
	for key, attribute in RESTRICTION_FILTERS.items():
		if filters.get(key):
			with_value = (
				frappe.qb.from_(ivr).select(ivr.parent)
				.where((ivr.attribute == attribute.format(bm=bm)) & (ivr.allowed_values == filters[key]))
			)
			query = query.where(it.name.isin(with_value))
	if filters.get("template"):
		query = query.where(it.name == filters["template"])
	return query.run(as_dict=1)


def get_restriction_values(templates, attributes):
	"""{template: {attribute: [allowed values of each row]}}"""
	ivr = frappe.qb.DocType("Item Variant Restrictions")
	values = {}
	for chunk in chunks(templates):
		rows = (
			frappe.qb.from_(ivr)
			.select(ivr.parent, ivr.attribute, IfNull(ivr.allowed_values, "-"))
			.where(ivr.parent.isin(chunk) & ivr.attribute.isin(attributes))
			.orderby(ivr.idx)
			.run()
		)
		for parent, attribute, allowed in rows:
			values.setdefault(parent, {}).setdefault(attribute, []).append(allowed)
	return values


def get_counts(templates):
	"""({template: variants}, {template: published web variants}, {template: its Website Item published})"""
	it = frappe.qb.DocType("Item")
	wi = frappe.qb.DocType("Website Item")
	variants, web_variants, published = {}, {}, {}
	for chunk in chunks(templates):
		variants.update(dict(frappe.qb.from_(it).select(it.variant_of, Count(it.name))
			.where(it.variant_of.isin(chunk)).groupby(it.variant_of).run()))
		web_variants.update(dict(frappe.qb.from_(wi).select(wi.variant_of, Count(wi.name))
			.where(wi.variant_of.isin(chunk) & (wi.published == 1)).groupby(wi.variant_of).run()))
		published.update(dict(frappe.qb.from_(wi).select(wi.item_code, Max(wi.published))
			.where(wi.item_code.isin(chunk)).groupby(wi.item_code).run()))
	return variants, web_variants, published
