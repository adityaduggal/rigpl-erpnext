# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
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
	conditions_it = get_conditions(filters)
	if filters.get("restrictions") == 1:
		query = """
			SELECT
				it.name, ivr.name, ivr.idx, ivr.attribute, ivr.allowed_values,
				ivr.is_numeric, ivr.rule
			FROM 
				`tabItem` it, `tabItem Variant Restrictions` ivr
			WHERE 
				ivr.parent = it.name %s
			ORDER BY
				it.name, ivr.idx""" %(conditions_it)
	else:
		query = """
			SELECT
				it.name, it.variant_of, iva.name, iva.idx,iva.attribute, iva.use_in_description,
				iva.prefix, iva.field_name, iva.suffix, iva.attribute_value, iva.numeric_values,
				iva.from_range, iva.increment, iva.to_range
			FROM 
				`tabItem` it, `tabItem Variant Attribute` iva
			WHERE 
				iva.parent = it.name %s
			ORDER BY
				it.name, iva.idx""" %(conditions_it)

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
		
	if filters.get("restrictions") == 1:
		if filters.get("template") == 1:
			pass
		else:
			frappe.throw("Restrictions Table can only be shown for Templates")
	
	
	return conditions_it