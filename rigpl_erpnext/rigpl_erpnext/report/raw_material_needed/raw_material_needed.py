# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_columns()
	data = get_items(filters)

	return columns, data

def get_columns():
	return [
			"Item:Link/Item:130",
			###Below are attribute fields
			"RM::30", "Brand::60", "Qual::80", "SPL::50", "TT::120",
			"D1:Float:50", "W1:Float:50", "L1:Float:50",
			###Above are Attribute fields
			"Future Stock::100", "Current Stock::100",
			"Lead Time:Int:50", "Total:Float:50",
			"RO:Float:40", "SO:Float:40", "PO:Float:40",
			"PL:Float:40", "IND:Float:50", "PRD:Float:50",
			"Description::300",
			"BRM:Float:50", "DRM:Float:50", "BGH:Float:50", "DEL:Float:50",
			"Dead:Float:50",
	]

def get_items(filters):
	conditions, params = get_conditions(filters)
	
	# 1. Base Item Fetch
	items = frappe.db.sql(f"""
		SELECT 
			it.name, it.description, it.lead_time_days,
			(SELECT warehouse_reorder_level FROM `tabItem Reorder` WHERE parent = it.name LIMIT 1) as rol
		FROM `tabItem` it
		WHERE it.is_purchase_item = 1 AND it.has_variants = 0 AND it.disabled = 0
		AND IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
		AND EXISTS (SELECT 1 FROM `tabBin` WHERE item_code = it.name)
		{conditions}
	""", params, as_dict=1)
	
	if not items:
		return []

	item_codes = [d.name for d in items]
	
	# 2. Bulk Fetch Attributes
	attr_map = get_attribute_map(item_codes, filters.get("bm"))
	
	# 3. Bulk Fetch Bin Data
	bin_map = get_bulk_bin_data(item_codes)
	
	actual_data = []
	for itm in items:
		res = attr_map.get(itm.name, {})
		bins = bin_map.get(itm.name, {})
		
		# Metric Extraction
		rol = flt(itm.rol)
		so = flt(bins.get("reserved", 0))
		po = flt(bins.get("ordered", 0))
		plan = flt(bins.get("planned", 0))
		ind = flt(bins.get("indented", 0))
		prd = flt(bins.get("prd", 0))
		
		# Specific Warehouse Bucketing
		brm = flt(bins.get("RM-BGH655 - RIGPL", 0))
		drm = flt(bins.get("RM-DEL20A - RIGPL", 0))
		bgh = flt(bins.get("BGH655 - RIGPL", 0))
		del20a = flt(bins.get("DEL20A - RIGPL", 0))
		dead = flt(bins.get("Dead Stock - RIGPL", 0))

		total = (drm + brm + plan + po + ind + bgh + del20a + dead) - prd
		stock = drm + brm + bgh + del20a + dead - prd
		
		# Calculated ROL Scaling Logic
		calc_rol = rol
		if rol < 10: calc_rol = 3 * rol
		elif 10 <= rol < 20: calc_rol = 2 * rol
		elif 20 <= rol < 50: calc_rol = 1.5 * rol

		# Stock Status Bucketing Logic
		def get_stock_status(qty, base_so, base_rol):
			if qty < base_so: return "Raise More PO and Indent"
			if qty < base_so + base_rol: return "1<30 Days"
			if qty < base_so + 2 * base_rol: return "2<60 Days"
			if qty < base_so + 3 * base_rol: return "3<90 Days"
			if qty < base_so + 4 * base_rol: return "4<120 Days"
			if qty < base_so + 5 * base_rol: return "5<150 Days"
			if qty < base_so + 6 * base_rol: return "6<180 Days"
			if qty > base_so + 6 * base_rol:
				return "7 Over Stocked >180 Days" if base_rol > 0 else "-"
			return "-"

		fut_stock = get_stock_status(total, so, calc_rol)
		cur_stock = "NO STOCK" if stock < calc_rol else get_stock_status(stock, so, calc_rol)

		row = [
			itm.name, res.get("Is RM", "-"), res.get("Brand", "-"), 
			res.get("Quality", "-"), res.get("Special Treatment", "-"),
			res.get("Tool Type", "-"), flt(res.get("d1_mm")), flt(res.get("w1_mm")), flt(res.get("l1_mm")), 
			fut_stock, cur_stock, itm.lead_time_days, total, rol, so, po, plan, ind, prd, itm.description,
			brm, drm, bgh, del20a, dead
		]
		# Cleaning up 0 values to None
		actual_data.append([x if x != 0 else None for x in row])

	# Sort Order
	actual_data.sort(key=lambda x: (str(x[1]), str(x[2]), str(x[4]), str(x[5]), flt(x[6]), flt(x[7]), flt(x[8])))
	
	return actual_data

def get_attribute_map(item_codes, bm_filter):
	if not item_codes: return {}
	quality_attr = f"{bm_filter} Quality" if bm_filter else "Quality"
	attrs_to_fetch = ["Is RM", "Brand", "Tool Type", "Special Treatment", "d1_mm", "w1_mm", "l1_mm", quality_attr]
	
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

def get_bulk_bin_data(item_codes):
	if not item_codes: return {}
	bins = frappe.db.sql("""
		SELECT 
			item_code, warehouse, actual_qty, reserved_qty, 
			ordered_qty, planned_qty, indented_qty, reserved_qty_for_production as prd
		FROM `tabBin` WHERE item_code IN %s
	""", (tuple(item_codes),), as_dict=1)
	
	res = {}
	for b in bins:
		if b.item_code not in res: 
			res[b.item_code] = {"reserved": 0, "ordered": 0, "planned": 0, "indented": 0, "prd": 0}
		
		d = res[b.item_code]
		d[b.warehouse] = b.actual_qty
		d["reserved"] += b.reserved_qty
		d["ordered"] += b.ordered_qty
		d["planned"] += b.planned_qty
		d["indented"] += b.indented_qty
		d["prd"] += b.prd
	return res

def get_conditions(filters):
	conditions = ""
	params = {}
	
	attr_filters = {
		"rm": "Is RM", "bm": "Base Material", "brand": "Brand", 
		"quality": "Quality", "spl": "Special Treatment", "tt": "Tool Type"
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

	if filters.get("show_in_website") == 1:
		conditions += " AND it.show_in_website = 1"

	if filters.get("item"):
		conditions += " AND it.name = %(item)s"
		params["item"] = filters.get("item")

	if filters.get("variant_of"):
		conditions += " AND it.variant_of = %(variant_of)s"
		params["variant_of"] = filters.get("variant_of")

	return conditions, params


