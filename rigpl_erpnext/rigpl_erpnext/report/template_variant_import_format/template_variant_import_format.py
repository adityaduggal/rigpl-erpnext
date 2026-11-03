# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import cint

def execute(filters=None):
	filters = filters or {}
	columns = get_columns(filters)
	data = get_items(filters)
	return columns, data
	
def get_columns(filters):
	if filters.get("restrictions") == 1:
		return [
			"Item:Link/Item:250", "Rest ID::100", "Rest IDX::50", "Attribute Name::150", 
			"Allowed Values::150", "Is Numeric::50", "Rule::250"
		]
	else:
		return [
			"Item:Link/Item:250", "Variant Of:Link/Item:250", "Att ID::100", "IDX::50",
			"Attribute Name::100", "In Desc::50", "Prefix::50","Field Name::80", 
			"Suffix::50", "Attribute Value::150", "Is Numeric:Int:50", "From Range:Float:80",
			"Increment:Float:80","To Range:Float:80"
		]

def get_items(filters):
	template = cint(filters.get("template"))
	if filters.get("restrictions") == 1 and not template:
		frappe.throw("Restrictions Table can only be shown for Templates", title="Templates Only")
	it = frappe.qb.DocType("Item")
	if filters.get("restrictions") == 1:
		child = frappe.qb.DocType("Item Variant Restrictions")
		query = frappe.qb.from_(it).join(child).on(child.parent == it.name).select(
			it.name, child.name, child.idx, child.attribute, child.allowed_values, child.is_numeric, child.rule)
	else:
		child = frappe.qb.DocType("Item Variant Attribute")
		query = frappe.qb.from_(it).join(child).on(child.parent == it.name).select(
			it.name, it.variant_of, child.name, child.idx, child.attribute, child.use_in_description, child.prefix,
			child.field_name, child.suffix, child.attribute_value, child.numeric_values, child.from_range,
			child.increment, child.to_range)
	query = query.where(it.has_variants == template).orderby(it.name).orderby(child.idx)
	if filters.get("eol"):
		query = query.where(IfNull(it.end_of_life, "2099-12-31") > filters["eol"])
	if filters.get("show_in_website") == 1:
		query = query.where(it.pl_item == 1)
	if filters.get("item"):
		query = query.where(it.name == filters["item"])
	if filters.get("variant_of"):
		query = query.where(it.variant_of.like("%{0}%".format(filters["variant_of"])))
	return query.run(as_list=1)
