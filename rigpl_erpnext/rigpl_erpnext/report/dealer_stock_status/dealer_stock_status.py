# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt


def execute(filters=None):
	if not filters: filters = {}
	
	wh_dict = frappe.db.sql("""SELECT name, listing_serial, short_code, warehouse_type FROM `tabWarehouse`
		WHERE disabled=0 AND is_group=0 AND listing_serial != 0 and is_subcontracting_warehouse = 0
		ORDER BY listing_serial ASC""", as_dict=1)
	
	columns = get_columns()
	data = get_items(filters, wh_dict)
	return columns, data


def get_columns():
	return [
		"Item:Link/Item:120",

		# Below are attribute fields
		"Series::60", "Qual::50", "SPL::100","TT::150", "D1:Float:50", "W1:Float:50", "L1:Float:60",
		"D2:Float:50", "L2:Float:60", "Zn:Int:40",
		# Above are Attribute fields

		"Description::500", "Ready Stock:Int:100", "WIP:Int:50", "Reserved:Int:80", "Total:Int:100"
	]


def get_items(filters, wh_dict):
	conditions, params = get_conditions(filters)
	
	# 1. Base Item Fetch
	items = frappe.db.sql(f"""
		SELECT it.name, it.description
		FROM `tabItem` it
		WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE() AND it.is_sales_item = 1 
		{conditions}
	""", params, as_dict=1)
	
	if not items:
		return []

	item_codes = [d.name for d in items]
	
	# 2. Bulk Fetch Attributes (O(1) mapping)
	attr_map = get_attribute_map(item_codes, filters.get("bm"))
	
	# 3. Bulk Fetch Bin Data (Eliminates N+1 loop)
	bin_map = get_bulk_bin_data(item_codes)
	
	actual_data = []
	for it in items:
		attrs = attr_map.get(it.name, {})
		
		# Stock logic aggregation
		res_val, on_po_val, plan_val, prd_val, total_val, ready_val, wip_val = 0, 0, 0, 0, 0, 0, 0
		on_so_val = 0
		
		# Warehouse buckets
		wh_actuals = {} # scode -> qty
		
		item_bins = bin_map.get(it.name, [])
		for b in item_bins:
			if b.subcon == 1:
				wip_val += flt(b.actual)
			else:
				wip_val += flt(b.on_po)
				on_so_val += flt(b.on_so)
				prd_val += flt(b.prd)
				plan_val += flt(b.plan)
				
				if b.scode:
					wh_actuals[b.scode] = flt(b.actual)
					
		# Derived Reserved
		res_val = on_so_val + prd_val
		
		# Finished Stock Bucketing
		for wh in wh_dict:
			scode = wh.short_code
			val = wh_actuals.get(scode, 0)
			if wh.warehouse_type in ("Finished Stock", "Dead Stock"):
				ready_val += val
			elif wh.warehouse_type != "Recoverable Stock":
				wip_val += val
				
		total_val = ready_val + wip_val - res_val
		
		row = [
			it.name, attrs.get("Series", "-"), attrs.get("Quality", "-"),
			attrs.get("Special Treatment", "-"), attrs.get("Tool Type", "-"),
			flt(attrs.get("d1_mm")), flt(attrs.get("w1_mm")), flt(attrs.get("l1_mm")),
			flt(attrs.get("d2_mm")), flt(attrs.get("l2_mm")), flt(attrs.get("Number of Flutes Zn")),
			it.description,
			ready_val if ready_val > 0 else None,
			wip_val if wip_val > 0 else None,
			res_val if res_val > 0 else None,
			total_val if total_val > 0 else None
		]
		actual_data.append(row)
		
	# Sorting logic preservation
	actual_data.sort(key=lambda x: (
		str(attr_map.get(x[0], {}).get("Is RM", "-")),
		str(attr_map.get(x[0], {}).get("Brand", "-")),
		str(x[3]), str(x[4]), flt(x[5]), flt(x[6]), flt(x[7]),
		flt(x[8]), flt(x[9])
	))
	
	return actual_data


def get_attribute_map(item_codes, bm_filter):
	if not item_codes: return {}
	quality_attr = f"{bm_filter} Quality" if bm_filter else "Quality"
	attrs_to_fetch = ["Series", "Is RM", "Brand", "Tool Type", "Special Treatment", "d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm", "Number of Flutes Zn", quality_attr]
	
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
		SELECT bn.item_code, bn.reserved_qty as on_so, bn.actual_qty as actual, 
			   bn.reserved_qty_for_production as prd, bn.ordered_qty as on_po, 
			   bn.planned_qty as plan, wh.is_subcontracting_warehouse as subcon,
			   wh.short_code as scode
		FROM `tabBin` bn
		INNER JOIN `tabWarehouse` wh ON wh.name = bn.warehouse
		WHERE bn.item_code IN %s
	""", (tuple(item_codes),), as_dict=1)
	
	res = {}
	for b in bins:
		if b.item_code not in res: res[b.item_code] = []
		res[b.item_code].append(b)
	return res


def get_conditions(filters):
	conditions = ""
	params = {}
	
	attr_filters = {
		"bm": "Base Material", "brand": "Brand", "quality": "Quality",
		"spl": "Special Treatment", "tt": "Tool Type", "series": "Series"
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

	return conditions, params

