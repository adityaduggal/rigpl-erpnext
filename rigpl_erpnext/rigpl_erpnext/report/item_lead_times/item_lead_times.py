# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from ....utils.lead_time_utils import get_detailed_manuf_lead_time_for_item, get_item_lead_time
from ....utils.purchase_utils import get_detailed_po_lead_time_for_item

def execute(filters=None):
	if not filters:
		filters = {}
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	if filters.get("detail") == 1:
		return [
			"Item:Link/Item:130",
			{
				"label": "Avg Based On",
				"fieldname": "based_on",
				"width": 10
			},
			{
				"label": "Trans #",
				"fieldname": "link_name",
				"fieldtype": "Dynamic Link",
				"options": "based_on",
				"width": 120
			},
			"Trans Date:Date:100", "S No Trans:Int:50", "Qty Trans:Float:100",
			"Curr Lead:Int:80", "Min Days Trans:Int:80", "Max Days Trans:Int:80", "Avg Days:Int:80",
			"Trans Weight:Int:80", "No of Sub Trans:Int:80",
			{
				"label": "Sub Trans Type",
				"fieldname": "sub_trans_type",
				"width": 10
			},
			{
				"label": "Sub Trans #",
				"fieldname": "sub_link_name",
				"fieldtype": "Dynamic Link",
				"options": "sub_trans_type",
				"width": 120
			},
			"Date Sub Trans:Date:80", "Qty Sub Trans:Float:80",
			"Days Sub Trans:Int:80", "Wt Sub Trans:Int:80","Description::450"
		]
	else:
		return [
				"Item:Link/Item:130", "ROL:Int:60", "Avg Based On::90",
				"# Transactions:Int:80", "Total Qty:Float:80", "Min Days:Int:80",
				"Max Days:Int:80", "Current Lead Time:Int:80", "Calculated Lead Time:Int:80",
				"Lead Time Diff:Int:80",
				"BM::60", "Brand::60", "Quality::60", "TT::130", "SPL::50",
				"D1 MM:Float:50", "W1 MM:Float:50", "L1 MM:Float:60",
				"D2 MM:Float:50", "L2 MM:Float:60",
				"Description::450", "Template:Link/Item:150"
		]


def get_data(filters):
	data = []
	conditions, params = get_conditions(filters)
	
	if filters.get("detail") == 1:
		it_name = filters.get("item")
		itd = frappe.get_all("Item", filters={"name": it_name}, fields=["name", "description", "lead_time_days", "include_item_in_manufacturing"])[0]
		if itd.include_item_in_manufacturing == 1:
			ld_dt = get_detailed_manuf_lead_time_for_item(itd.name, frm_dt=filters.get("from_date"),
				to_dt=filters.get("to_date"))
		else:
			ld_dt = get_detailed_po_lead_time_for_item(itd.name, frm_dt=filters.get("from_date"),
				to_dt=filters.get("to_date"))
		for ldt in ld_dt:
			base_row = [
				itd.name, ldt.based_on, ldt.trans_name, ldt.calc_trans_date, ldt.idx, ldt.trans_qty,
				itd.lead_time_days, ldt.trans_min_days, ldt.trans_max_days, ldt.trans_avg_days,
				ldt.trans_wt, len(ldt.sub_trans)
			]
			for sub in ldt.sub_trans:
				row = base_row + [sub.sub_trans_type, sub.sub_trans_name, sub.sub_trans_date,
				sub.sub_trans_qty, sub.days_diff, sub.sub_trans_wt, itd.description]
				data.append(row)
	else:
		# 1. Base Item Fetch
		items = frappe.db.sql(f"""
			SELECT it.name, it.description, it.variant_of, it.lead_time_days as ex_lead,
				   rol.warehouse_reorder_level as existing_rol
			FROM `tabItem` it
			LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent AND rol.parentfield = 'reorder_levels'
			WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
			{conditions}
		""", params, as_dict=1)
		
		if not items:
			return []

		item_codes = [d.name for d in items]
		
		# 2. Bulk Fetch Attributes (O(1) mapping)
		attr_map = get_attribute_map(item_codes, filters.get("bm"))
		
		# 3. Calculation Loop (Semi-Optimized)
		frm_dt = filters.get("from_date")
		to_dt = filters.get("to_date")
		
		for itm in items:
			# Calling utility; although still N hits, the complexity of FIFO logic 
			calc_dict = get_item_lead_time(item_name=itm.name, frm_dt=frm_dt, to_dt=to_dt)
			
			attrs = attr_map.get(itm.name, {})
			avg_days_wt = calc_dict.get("avg_days_wt", 0)
			
			row = [
				itm.name, itm.existing_rol, calc_dict.get("based_on"), 
				calc_dict.get("no_of_trans"), calc_dict.get("total_qty", 0), 
				calc_dict.get("min_days", 0), calc_dict.get("max_days", 0), 
				itm.ex_lead, avg_days_wt, (avg_days_wt - itm.ex_lead),
				attrs.get("Base Material", "-"), attrs.get("Brand", "-"),
				attrs.get("Quality", "-"), attrs.get("Tool Type", "-"),
				attrs.get("Special Treatment", "-"),
				flt(attrs.get("d1_mm")), flt(attrs.get("w1_mm")), flt(attrs.get("l1_mm")),
				flt(attrs.get("d2_mm")), flt(attrs.get("l2_mm")),
				itm.description, itm.variant_of
			]
			data.append(row)
			
		# sort order
		data.sort(key=lambda x: (
			str(x[10]), str(x[12]), str(x[13]), flt(x[15]), flt(x[16]), 
			flt(x[18]), flt(x[19])
		))
		
	return data

def get_attribute_map(item_codes, bm_filter):
	if not item_codes: return {}
	quality_attr = f"{bm_filter} Quality" if bm_filter else "Quality"
	attrs_to_fetch = ["Base Material", "Brand", "Tool Type", "Special Treatment", "d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm", quality_attr]
	
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

def get_conditions(filters):
	conditions = ""
	params = {}
	
	attr_filters = {
		"rm": "Is RM", "bm": "Base Material", "brand": "Brand", 
		"quality": "Quality", "tt": "Tool Type"
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

