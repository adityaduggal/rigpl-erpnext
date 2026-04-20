# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_items(filters)
	
	return columns, data
	
def get_columns():
	return [
		"Item:Link/Item:100", "Description::300", "PL::35",
		"SO::35", "PO::35","Web::35", "TOD::35",
		"#SO:Int:40", "#SI:Int:40", "#PO:Int:40", "#PI:Int:40",
		"#SLE:Int:40", "#STE:Int:40", "#SR:Int:40", "#PRD:Int:40",
		"VR:Currency:100",
		"Created By:Link/User:150", "Creation:Date:130"
	]

def get_items(filters):
	conditions, params = get_conditions(filters)

	# Pre-check row count
	pre_data = frappe.db.sql(f"""SELECT it.name FROM `tabItem` it
		{conditions}""", params, as_list=1)
	
	# if len(pre_data) > 500:
	# 	frappe.throw(("Server overload possible due to {0} rows of data, kindly reduce \
	# 		the lines by selecting filters").format(len(pre_data)))
	
	# 1. Base Item Fetch
	items = frappe.db.sql(f"""SELECT it.name, it.description, it.pl_item,
		it.is_sales_item, it.is_purchase_item, it.show_in_website,
		it.stock_maintained, it.valuation_rate,
		IFNULL(it.owner,'Administrator'), it.creation
		FROM `tabItem` it
		{conditions}""", params, as_list=1)
	
	if not items:
		return []

	item_codes = [d[0] for d in items]
	
	# 2. Bulk Fetch Transaction Counts
	count_maps = get_bulk_transaction_counts(item_codes)
	
	# 3. Assembly
	data = []
	for row in items:
		ic = row[0]
		counts = [count_maps[i].get(ic, 0) for i in range(8)]
		# Insert counts after position 6 (stock_maintained), before valuation_rate
		data.append(row[:7] + counts + row[7:])
	
	return data

def get_bulk_transaction_counts(item_codes):
	if not item_codes: return [{} for _ in range(8)]
	
	ic_tuple = tuple(item_codes)
	
	# Define all 8 transaction tables and their item_code field
	tables = [
		("`tabSales Order Item`", "item_code"),
		("`tabSales Invoice Item`", "item_code"),
		("`tabPurchase Order Item`", "item_code"),
		("`tabPurchase Invoice Item`", "item_code"),
		("`tabStock Ledger Entry`", "item_code"),
		("`tabStock Entry Detail`", "item_code"),
		("`tabStock Reconciliation Item`", "item_code"),
		("`tabWork Order`", "production_item"),
	]
	
	maps = []
	for table, field in tables:
		rows = frappe.db.sql(f"""
			SELECT {field}, COUNT(name) as cnt
			FROM {table}
			WHERE {field} IN %s
			GROUP BY {field}
		""", (ic_tuple,), as_dict=1)
		m = {}
		for r in rows:
			m[r[field]] = r.cnt
		maps.append(m)
	
	return maps

def get_conditions(filters):
	conditions = " WHERE 1=1 "
	params = {}
	
	if filters.get("eol"):
		conditions += " AND IFNULL(it.end_of_life, '2099-12-31') > %(eol)s"
		params["eol"] = filters["eol"]

	if filters.get("is_pl_item"):
		conditions += " AND it.pl_item ='Yes'"
	else:
		conditions += " AND it.pl_item ='No'"
		
	if filters.get("has_variants"):
		conditions += " AND it.has_variants = 1"
	else:
		conditions += " AND it.has_variants = 0"
		
	if filters.get("item"):
		conditions += " AND it.name = %(item)s"
		params["item"] = filters["item"]

	attr_filters = {
		"bm": "Base Material", "is_rm": "Is RM", "brand": "Brand",
		"spl": "Special Treatment", "tt": "Tool Type"
	}

	for f_key, attr_name in attr_filters.items():
		if filters.get(f_key):
			p_val = f"f_{f_key}"
			params[f"{p_val}_attr"] = attr_name
			params[f"{p_val}_val"] = filters.get(f_key)
			conditions += f" AND EXISTS (SELECT 1 FROM `tabItem Variant Attribute` WHERE parent = it.name AND attribute = %({p_val}_attr)s AND attribute_value = %({p_val}_val)s)"

	if filters.get("quality"):
		params["f_quality_val"] = filters.get("quality")
		conditions += " AND EXISTS (SELECT 1 FROM `tabItem Variant Attribute` WHERE parent = it.name AND attribute LIKE '%%Quality' AND attribute_value = %(f_quality_val)s)"

	return conditions, params