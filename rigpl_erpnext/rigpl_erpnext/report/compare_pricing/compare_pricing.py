# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	if not filters: filters = {}
	else: filters = frappe._dict(filters)

	if not filters.pl1 or not filters.pl2 or not filters.pl3:
		frappe.throw(_("Please select all three Price Lists for comparison."))

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
			"fieldtype": "Float",
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
			"fieldtype": "Float",
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
	conditions, params = get_conditions(filters)
	
	# 1. Base Item Fetch
	items = frappe.db.sql(f"""
		SELECT it.name, it.description, it.pl_item
		FROM `tabItem` it
		WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
		{conditions}
	""", params, as_dict=1)
	
	if not items:
		return []

	item_codes = [d.name for d in items]
	
	# 2. Bulk Fetch Attributes (O(1) Memory Mapping)
	attr_map = get_attribute_map(item_codes, filters.bm)
	
	# 3. Bulk Fetch Prices (Single query for all 3 price lists)
	price_map = get_price_map(item_codes, [filters.pl1, filters.pl2, filters.pl3])

	# 4. Assembly
	data = []
	for it in items:
		attrs = attr_map.get(it.name, {})
		prices = price_map.get(it.name, {})
		
		p1 = prices.get(filters.pl1, frappe._dict({"rate": 0, "cur": "-"}))
		p2 = prices.get(filters.pl2, frappe._dict({"rate": 0, "cur": "-"}))
		p3 = prices.get(filters.pl3, frappe._dict({"rate": 0, "cur": "-"}))
		
		# Calculate Percentage Diffs
		diff2 = ((flt(p2.rate) - flt(p1.rate)) / flt(p1.rate)) * 100 if flt(p1.rate) > 0 else 0
		diff3 = ((flt(p3.rate) - flt(p1.rate)) / flt(p1.rate)) * 100 if flt(p1.rate) > 0 else 0
		
		data.append([
			it.name, p1.rate, p1.cur, p2.rate, p2.cur, diff2, p3.rate, p3.cur, diff3,
			it.description, attrs.get("Base Material", "-"), attrs.get("Brand", "-"),
			attrs.get("Quality", "-"), attrs.get("Special Treatment", "-"),
			attrs.get("Tool Type", "-"), flt(attrs.get("d1_mm")), flt(attrs.get("w1_mm")),
			flt(attrs.get("l1_mm")), flt(attrs.get("Number of Flutes (Zn)")),
			flt(attrs.get("d2_mm")), flt(attrs.get("l2_mm")), flt(attrs.get("a1_deg")),
			it.pl_item
		])

	# sort order in Python
	data.sort(key=lambda x: (
		str(x[10]), str(x[11]), str(x[12]), str(x[14]),
		flt(x[15]), flt(x[16]), flt(x[17]), flt(x[18]),
		flt(x[19]), flt(x[20]), str(x[13])
	))
	
	return data


def get_attribute_map(item_codes, bm_filter):
	if not item_codes: return {}
	quality_attr = f"{bm_filter} Quality" if bm_filter else "Quality"
	attrs_to_fetch = [
		"Base Material", "Brand", "Tool Type", "Special Treatment", 
		"d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm", "a1_deg",
		"Number of Flutes (Zn)", quality_attr
	]
	
	raw_attrs = frappe.get_all("Item Variant Attribute",
		filters={"parent": ["in", item_codes], "attribute": ["in", attrs_to_fetch]},
		fields=["parent", "attribute", "attribute_value"]
	)
	
	res = {}
	for a in raw_attrs:
		if a.parent not in res: res[a.parent] = {}
		key = "Quality" if a.attribute == quality_attr else a.attribute
		res[a.parent][key] = a.attribute_value
	return res


def get_price_map(item_codes, price_lists):
	# Fetch all prices for all 3 price lists in a single indexed query
	price_data = frappe.db.sql("""
		SELECT item_code, price_list, price_list_rate as rate, IFNULL(currency, "-") as cur
		FROM `tabItem Price`
		WHERE item_code IN %s AND price_list IN %s
	""", (tuple(item_codes), tuple(price_lists)), as_dict=1)
	
	res = {}
	for p in price_data:
		if p.item_code not in res: res[p.item_code] = {}
		res[p.item_code][p.price_list] = p
	return res


def get_conditions(filters):
	conditions = ""
	params = {}
	
	attr_filters = {
		"bm": "Base Material", "brand": "Brand", "quality": "Quality",
		"spl": "Special Treatment", "purpose": "Purpose", "type": "Type Selector",
		"mtm": "Material to Machine", "tt": "Tool Type"
	}

	for f_key, attr_name in attr_filters.items():
		if filters.get(f_key):
			actual_attr = attr_name
			if f_key == "quality" and filters.get("bm"):
				actual_attr = f"{filters.get('bm')} Quality"
			
			p_val = f"f_{f_key}"
			params[f"{p_val}_attr"] = actual_attr
			params[f"{p_val}_val"] = filters.get(f_key)
			conditions += f" AND EXISTS (SELECT 1 FROM `tabItem Variant Attribute` WHERE parent = it.name AND attribute = %({p_val}_attr)s AND attribute_value = %({p_val}_val)s)"

	if filters.get("item"):
		conditions += " AND it.name = %(item)s"
		params["item"] = filters.get("item")

	if filters.get("template"):
		conditions += " AND it.variant_of = %(template)s"
		params["template"] = filters.get("template")

	if filters.get("is_pl") == 1:
		conditions += " AND it.pl_item = 'Yes'"

	return conditions, params
