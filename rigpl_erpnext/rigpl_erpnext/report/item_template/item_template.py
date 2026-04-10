# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = frappe._dict({})
	else: filters = frappe._dict(filters)
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
	conditions, params = get_conditions(filters)
	
	# 1. Base Item Fetch
	items = frappe.db.sql(f"""
		SELECT 
			it.name, it.variant_limit, it.item_group, it.default_warehouse, 
			it.valuation_method, it.tolerance, it.is_purchase_item,
			it.is_sales_item, it.show_in_website, it.pl_item, it.is_pro_applicable,
			it.image 
		FROM `tabItem` it
		WHERE it.has_variants = 1
		{conditions}
	""", params, as_dict=1)
	
	if not items:
		return []

	item_codes = [d.name for d in items]
	
	# 2. Bulk Fetch Variant Counts
	variant_counts = get_bulk_variant_counts(item_codes)
	
	# 3. Bulk Fetch Restrictions
	restriction_map = get_restriction_map(item_codes, filters.get("bm"))
	
	# 4. Assembly
	data = []
	for it in items:
		counts = variant_counts.get(it.name, {"total": 0, "web": 0})
		res = restriction_map.get(it.name, {})
		
		data.append([
			it.name, counts["total"], it.variant_limit,
			res.get("Is RM", "-"), res.get("Base Material", "-"),
			res.get("Brand", "-"), res.get("Quality", "-"),
			res.get("Special Treatment", "-"), res.get("Tool Type", "-"),
			res.get("Material to Machine", "-"), res.get("Purpose", "-"),
			it.item_group, it.default_warehouse, it.valuation_method,
			it.tolerance, it.is_purchase_item,
			it.is_sales_item, it.show_in_website, counts["web"],
			it.pl_item, it.is_pro_applicable,
			res.get("CETSH Number", "-"), None, None, None, it.image or "-"
		])
				
	return data

def get_bulk_variant_counts(item_codes):
	# Fetch all variant counts and web variants at once
	res = {ic: {"total": 0, "web": 0} for ic in item_codes}
	
	counts = frappe.db.sql("""
		SELECT variant_of, COUNT(name) as total, SUM(IF(show_variant_in_website=1, 1, 0)) as web
		FROM `tabItem` 
		WHERE variant_of IN %s AND has_variants = 0
		GROUP BY variant_of
	""", (tuple(item_codes),), as_dict=1)
	
	for c in counts:
		res[c.variant_of] = {"total": c.total, "web": c.web}
	return res

def get_restriction_map(item_codes, bm_filter):
	quality_attr = f"{bm_filter} Quality" if bm_filter else "Quality"
	attrs_to_fetch = ['Is RM', 'Base Material', 'Brand', quality_attr, 'Special Treatment',
		'Tool Type', 'Material to Machine', 'Purpose', 'CETSH Number']
	
	raw_res = frappe.get_all("Item Variant Restrictions",
		filters={"parent": ["in", item_codes], "attribute": ["in", attrs_to_fetch]},
		fields=["parent", "attribute", "allowed_values"]
	)
	
	mapping = {}
	for r in raw_res:
		if r.parent not in mapping: mapping[r.parent] = {}
		key = "Quality" if r.attribute == quality_attr else r.attribute
		mapping[r.parent][key] = r.allowed_values
	return mapping

def get_conditions(filters):
	conditions = ""
	params = {}
	
	attr_filters = {
		"rm": "Is RM", "bm": "Base Material", "brand": "Brand", 
		"quality": "Quality", "spl": "Special Treatment", "purpose": "Purpose",
		"type": "Type Selector", "mtm": "Material to Machine", "tt": "Tool Type"
	}

	for f_key, attr_name in attr_filters.items():
		if filters.get(f_key):
			actual_attr = attr_name
			if f_key == "quality" and filters.get("bm"):
				actual_attr = f"{filters.get('bm')} Quality"
			
			p_val = f"f_{f_key}"
			params[f"{p_val}_attr"] = actual_attr
			params[f"{p_val}_val"] = filters.get(f_key)
			conditions += f" AND EXISTS (SELECT 1 FROM `tabItem Variant Restrictions` WHERE parent = it.name AND attribute = %({p_val}_attr)s AND allowed_values = %({p_val}_val)s)"

	if filters.get("template"):
		conditions += " AND it.name = %(item)s"
		params["item"] = filters.get("template")

	return conditions, params
