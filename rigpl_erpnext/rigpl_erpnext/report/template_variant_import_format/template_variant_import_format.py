# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns = get_columns(filters)
	data = get_items(filters)
	return columns, data
	
def get_columns(filters):
	return [
		"Item:Link/Item:250", "Att ID::100", "Attribute Name::100", "In Desc::50", 
		"Prefix::50","Field Name::80", 
		"Suffix::50", "Attribute Value::50", "Is Numeric:Int:50", "From Range:Float:80",
		"Increment:Float:80","To Range:Float:80"
	]

def get_items(filters):
	conditions_it = get_conditions(filters)
	query = """
		SELECT
			it.name, iva.name, iva.attribute, iva.use_in_description, iva.prefix,
			iva.field_name, iva.suffix, iva.attribute_value, iva.numeric_values, iva.from_range,
			iva.increment, iva.to_range
		FROM 
			`tabItem` it, `tabItem Variant Attribute` iva
		WHERE 
			iva.parent = it.name %s""" %(conditions_it)

	data = frappe.db.sql(query, as_list=1)
	
	return data

def get_conditions(filters):
	conditions_it = ""

	if filters.get("eol"):
		conditions_it += "AND IFNULL(it.end_of_life, '2099-12-31') > '%s'" % filters["eol"]
	
	if filters.get("show_in_website") ==1:
		conditions_it += " AND it.show_in_website =%s" % filters["show_in_website"]
	
	if filters.get("item"):
		conditions_it += " AND it.name = '%s'" % filters["item"]
	
	if filters.get("variant_of"):
		conditions_it += " AND it.variant_of = '%s'" % filters["variant_of"]
	
	if filters.get("template"):
		conditions_it += " AND it.has_variants = '%s'" % filters["template"]
	else:
		conditions_it += " AND it.has_variants = 0"
	
	
	return conditions_it