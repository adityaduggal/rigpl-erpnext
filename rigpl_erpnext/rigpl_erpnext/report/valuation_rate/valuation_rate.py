# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):
	if not filters: filters = {}
	bm = filters.get("bm")
	
	conditions_it, conditions_pl, params = get_conditions(bm, filters)
	templates = get_templates(conditions_it, params)
	
	columns, attributes, att_details = get_columns(templates)
	items = get_items(conditions_it, params, conditions_pl, attributes, att_details, filters)

	return columns, items
	
def get_columns(templates):
	columns = [
		_("Item") + ":Link/Item:130", 
		_("Rate") + ":Currency:80", _("Valuation Rate Date") + ":Date:80", 
		_("Base on PL") + ":Link/Price List:80", 
		_("PL Rate") + ":Currency:80", _("%age of PL") + ":Float:80",
		_("Set %age") + ":Float:80"
	]
	
	template_names = tuple(d.variant_of for d in templates)

	attributes = frappe.db.sql_list("""SELECT DISTINCT attribute
		FROM `tabItem Variant Attribute`
		WHERE parent IN %s
		ORDER BY idx""", (template_names,))
	
	att_details = []
	for i in attributes:
		attr_dict = {}
		att_name = frappe.db.sql("""SELECT name, attribute, field_name FROM `tabItem Variant Attribute` 
			WHERE attribute = %s AND parent IN %s GROUP BY field_name""", (i, template_names), as_dict=1)
		
		attr = frappe.get_doc("Item Attribute", i)
		attr_dict["name"] = i
		attr_dict["numeric_values"] = attr.numeric_values
		
		if attr.numeric_values != 1:
			max_length = frappe.db.sql("""SELECT MAX(CHAR_LENGTH(attribute_value))
				FROM `tabItem Attribute Value` WHERE parent = %s""", (i,), as_list=1)
			if attr.hidden == 1:
				s = att_name[0].field_name if att_name and att_name[0].field_name else ""
				n = i.split('_', 1)[1] if '_' in i else i
				nit = s.split('(', 1)[0] + "(" + n + ")" if '(' in s else s
				name_in_template = nit
			else:
				name_in_template = att_name[0].attribute if att_name else i
		else:
			max_length = [[6]]
			s = att_name[0].field_name if att_name and att_name[0].field_name else ""
			n = i.split('_', 1)[1] if '_' in i else i
			nit = s.split('(', 1)[0] + "(" + n + ")" if '(' in s else i
			name_in_template = nit
			
		attr_dict["max_length"] = int(max_length[0][0]) if max_length and max_length[0][0] else 10
		attr_dict["name_in_template"] = name_in_template
		att_details.append(attr_dict)

	for att in attributes:
		for i in att_details:
			if att == i["name"]:
				label = i["name_in_template"]
				max_val = min(i["max_length"], 10)
				width = 10 * max_val
				if i["numeric_values"] == 1:
					col = f":Float:{width}"
				else:
					col = f"::{width}"
				columns.append(label + col)
	
	columns.extend([
		_("Description") + "::400", _("EOL") + ":Date:80", _("Created By") + "::150",
		_("Creation") + ":Date:150"
	])
	
	return columns, attributes, att_details
	
def get_items(conditions_it, params, conditions_pl, attributes, att_details, filters):
	query = f"""SELECT it.name, it.valuation_rate, it.valuation_rate_date, itp.price_list, 
		itp.price_list_rate, (it.valuation_rate/itp.price_list_rate*100) as pl_per, 
		it.valuation_as_percent_of_default_selling_price, 
		it.description, IFNULL(it.end_of_life, '2099-12-31') as eol,
		IFNULL(it.owner, "X") as owner, it.creation
		FROM `tabItem` it
		LEFT JOIN `tabItem Price` itp ON it.name = itp.item_code {conditions_pl}
		{conditions_it}"""

	items = frappe.db.sql(query, params, as_dict=1)

	if not items: return []

	item_codes = [d.name for d in items]
	
	# Bulk Fetch Attributes
	item_attrs = {}
	if item_codes and attributes:
		chunk_size = 5000
		for i in range(0, len(item_codes), chunk_size):
			chunk = item_codes[i:i+chunk_size]
			attrs_data = frappe.db.sql("""
				SELECT parent, attribute, attribute_value
				FROM `tabItem Variant Attribute`
				WHERE parent IN %s AND attribute IN %s
			""", (tuple(chunk), tuple(attributes)), as_dict=1)
			
			for ad in attrs_data:
				item_attrs.setdefault(ad.parent, {})[ad.attribute] = ad.attribute_value

	res = []
	for d in items:
		# Standard columns
		row = [
			d.name, d.valuation_rate, d.valuation_rate_date, d.price_list,
			d.price_list_rate, d.pl_per, d.valuation_as_percent_of_default_selling_price
		]
		
		# Dynamic attribute columns
		sort_vals = []
		for att in attributes:
			detail = next((x for x in att_details if x["name"] == att), None)
			val = item_attrs.get(d.name, {}).get(att)
			if detail and detail["numeric_values"] == 1:
				num_val = flt(val) if val else 0.0
				row.append(num_val)
				sort_vals.append(num_val)
			else:
				str_val = val if val else "-"
				row.append(str_val)
				sort_vals.append(str_val)
		
		# Trailing standard columns
		row.extend([d.description, d.eol, d.owner, d.creation])
		
		# Store sort order wrapper
		res.append({"sort_key": tuple(sort_vals) + (d.name,), "row": row})

	# Sort mimicking OLD "ORDER BY att1, att2, ..., it.name"
	res.sort(key=lambda x: x["sort_key"])
	
	return [x["row"] for x in res]

def get_templates(conditions_it, params):
	query = f"""SELECT DISTINCT(it.variant_of) 
		FROM `tabItem` it {conditions_it} AND it.variant_of IS NOT NULL AND it.variant_of != ''"""
		
	templates = frappe.db.sql(query, params, as_dict=1)
	
	if not templates:
		frappe.throw("No Temps in the given Criterion")
	
	return templates
	
def get_conditions(bm, filters):
	conditions_it = " WHERE 1=1 "
	conditions_pl = ""
	params = {}
	
	if filters.get("pl"):
		conditions_pl += " AND itp.price_list = %(pl)s"
		params["pl"] = filters.get("pl")
		
	if filters.get("eol"):
		conditions_it += " AND IFNULL(it.end_of_life, '2099-12-31') > %(eol)s"
		params["eol"] = filters.get("eol")
	
	attr_filters = {
		"rm": "Is RM",
		"bm": "Base Material",
		"series": "Series",
		"quality": f"{bm} Quality",
		"spl": "Special Treatment",
		"purpose": "Purpose",
		"type": "Type Selector",
		"mtm": "Material to Machine",
		"tt": "Tool Type"
	}

	for f_key, attr_name in attr_filters.items():
		if filters.get(f_key):
			p_val = f"f_{f_key}"
			params[f"{p_val}_attr"] = attr_name
			params[f"{p_val}_val"] = filters.get(f_key)
			conditions_it += f" AND EXISTS (SELECT 1 FROM `tabItem Variant Attribute` WHERE parent = it.name AND attribute = %({p_val}_attr)s AND attribute_value = %({p_val}_val)s)"

	if filters.get("show_in_website") == 1:
		conditions_it += " AND it.show_in_website = 1"

	if filters.get("item"):
		conditions_it += " AND it.name = %(item)s"
		params["item"] = filters.get("item")
	
	if filters.get("variant_of"):
		conditions_it += " AND it.variant_of = %(variant_of)s"
		params["variant_of"] = filters.get("variant_of")
		
	return conditions_it, conditions_pl, params
