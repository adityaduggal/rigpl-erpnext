# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = {}
	columns = get_columns()
	data = get_items(filters)
	
	return columns, data
	
def get_columns():
	return[
		"Item:Link/Item:300", "# Variants:Int:50", "Limit:Int:50", "Is RM::50",
		"BM::60", "Brand::60", "Quality::60", "SPL::60", "TT::150", "MTM::60",
		"Purpose::60", "Item Group::200", "WH::150", "Valuation::60",
		"Tolerance:Int:40", "Purchase:Int:40", "Is Sale:Int:40",
		"PRD:Int:40", "CETSH::100", "D1_MM::50", "W1_MM::50", "L1_MM::50"
	]

def get_items(filters):
	conditions_it = get_conditions(filters)
	bm = filters["bm"]
	#List of fields to be fetched in the report
	attributes = ['Is RM', 'Base Material', 'Brand', '%Quality', 'Special Treatment',
		'Tool Type', 'd1_mm', 'd1_inch', 'w1_mm', 'w1_inch', 'l1_mm', 'l1_inch',
		'CETSH Number']
	
	float_fields = ['d1_mm', 'w1_mm', 'l1_mm']
	linked_fields = ['d1_inch', 'w1_inch', 'l1_inch']
	
	data = frappe.db.sql("""SELECT it.name, 
		(SELECT count(name) FROM `tabItem` WHERE variant_of = it.name),
		it.variant_limit,
		IFNULL(rm.allowed_values, "-"), IFNULL(bm.allowed_values, "-"),
		IFNULL(brand.allowed_values, "-"), IFNULL(quality.allowed_values, "-"), 
		IFNULL(spl.allowed_values, "-"), IFNULL(tt.allowed_values, "-"),
		IFNULL(mtm.allowed_values, "-"), IFNULL(purpose.allowed_values, "-"),
		it.item_group, it.default_warehouse, it.valuation_method,
		it.tolerance, it.is_purchase_item,
		it.is_sales_item, it.is_pro_applicable, 
		IFNULL(cetsh.allowed_values, "-")
		
		FROM `tabItem` it
		LEFT JOIN `tabItem Variant Restrictions` rm ON it.name = rm.parent
			AND rm.attribute = 'Is RM'
		LEFT JOIN `tabItem Variant Restrictions` bm ON it.name = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Restrictions` brand ON it.name = brand.parent
			AND brand.attribute = 'Brand'
		LEFT JOIN `tabItem Variant Restrictions` quality ON it.name = quality.parent
			AND quality.attribute = '%s Quality'
		LEFT JOIN `tabItem Variant Restrictions` spl ON it.name = spl.parent
			AND spl.attribute = 'Special Treatment'
		LEFT JOIN `tabItem Variant Restrictions` tt ON it.name = tt.parent
			AND tt.attribute = 'Tool Type'
		LEFT JOIN `tabItem Variant Restrictions` mtm ON it.name = mtm.parent
			AND mtm.attribute = 'Material to Machine'
		LEFT JOIN `tabItem Variant Restrictions` purpose ON it.name = purpose.parent
			AND purpose.attribute = 'Purpose'
		LEFT JOIN `tabItem Variant Restrictions` cetsh ON it.name = cetsh.parent
			AND cetsh.attribute = 'CETSH Number'
			
			
		WHERE it.has_variants = 1 %s """ % (bm, conditions_it) , as_list = 1)
		
	return data
	
def get_conditions(filters):
	conditions_it = ""

	if filters.get("rm"):
		conditions_it += " AND rm.allowed_values = '%s'" % filters["rm"]

	if filters.get("bm"):
		conditions_it += " AND bm.allowed_values = '%s'" % filters["bm"]

	if filters.get("brand"):
		conditions_it += " AND brand.allowed_values = '%s'" % filters["brand"]

	if filters.get("quality"):
		conditions_it += " AND quality.allowed_values = '%s'" % filters["quality"]

	if filters.get("spl"):
		conditions_it += " AND spl.allowed_values = '%s'" % filters["spl"]
		
	if filters.get("tt"):
		conditions_it += " AND tt.allowed_values = '%s'" % filters["tt"]

	return conditions_it