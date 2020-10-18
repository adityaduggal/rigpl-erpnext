# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from rigpl_erpnext.utils.manufacturing_utils import get_bom_template_from_item

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		"Item:Link/Item:150", "Description::400", "BOM Templates::300", "Variant Of:Link/Item:300"
	]

def get_data(filters):
	data = []
	it_conditions = get_conditions(filters)
	query = """SELECT it.name, it.description, it.variant_of FROM `tabItem` it 
	WHERE it.disabled = 0 AND it.include_item_in_manufacturing = 1 AND it.has_variants = 0 
	AND it.variant_of IS NOT NULL %s
	ORDER BY it.variant_of, it.name""" % it_conditions
	it_dict = frappe.db.sql(query, as_dict=1)
	for d in it_dict:
		line_data = []
		line_data.append(d.name)
		line_data.append(d.description)
		it_doc = frappe.get_doc("Item", d.name)
		bt_name = get_bom_template_from_item(it_doc, no_error=1)
		bt_names_concat = " "
		if bt_name:
			if len(bt_name) == 1:
				bt_names_concat += bt_name[0]
			else:
				for bt in bt_name:
					bt_names_concat += bt + ", "
		else:
			bt_names_concat = "No Applicable BOM Templates Found"
		line_data.append(bt_names_concat)
		line_data.append(d.variant_of)
		data.append(line_data)
	return data

def get_conditions(filters):
	it_conds = ""
	if filters.get("template"):
		it_conds += " AND it.variant_of = '%s'" % (filters.get("template"))

	return it_conds
