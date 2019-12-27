# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns = get_columns(filters)
	data = get_items(filters)

	return columns, data

def get_columns(filters):
	if filters.get("template") == 1:
		return ["Template:Link/Item:300", "Attribute:Link/Item Attribute:150", "Field Name::150", 
			"Disabled::50", "End Of Life:Date:80"]
	else:
		return ["Item:Link/Item:150", "Description::300", "Template:Link/Item:300", "Attribute::150", 
			"Attribute Value::150", "Disabled::50", "End Of Life:Date:80"]

def get_items(filters):
	conditions = get_conditions(filters)
	if filters.get("template") == 1:
		data = frappe.db.sql("""SELECT it.name, iva.attribute, iva.field_name, it.disabled, 
			IFNULL(it.end_of_life, '2099-12-31')
			FROM `tabItem` it, `tabItem Variant Attribute` iva
			WHERE iva.parent = it.name %s ORDER BY it.name, iva.idx""" %(conditions), as_list=1)
		return data
	else:
		data = frappe.db.sql("""SELECT it.name, it.description , it.variant_of, iva.attribute, iva.attribute_value,
			it.disabled, IFNULL(it.end_of_life, '2099-12-31')
			FROM `tabItem` it, `tabItem Variant Attribute` iva
			WHERE iva.parent = it.name %s ORDER BY it.name, iva.idx""" %(conditions), as_list=1)
		return data

def get_conditions(filters):
	conditions = ""
	if filters.get("template") == 1:
		conditions += " AND it.has_variants = 1"
	else:
		conditions += " AND it.has_variants = 0 AND it.variant_of IS NOT NULL"
	if filters.get("disabled") == 0:
		conditions += " AND it.disabled = 0"
	return conditions