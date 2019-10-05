# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_items(filters)

	return columns, data

def get_columns():
	return [
		"Item:Link/Item:120", 
		
		###Below are attribute fields
		"Series::60", "BM::60", "Brand::40", "Qual::50", "SPL::50", "TT::100",
		"MTM::60", "Purpose::100", "Type::60",
		"D1:Float:50", "W1:Float:50", "L1:Float:60",
		"D2:Float:50", "L2:Float:60", "Zn:Int:30",
		###Above are Attribute fields
		
		"Description::400", "Ready Stock:Int:60", "WIP1:Int:60", "WIP2:Int:60"
	]

def get_items(filters):
	conditions_it = get_conditions(filters)
	bm = filters["bm"]
	data = frappe.db.sql("""
	SELECT 
		it.name,
		IFNULL(series.attribute_value, "-"), IFNULL(bm.attribute_value, "-"),
		IFNULL(brand.attribute_value, "-"),
		IFNULL(quality.attribute_value, "-"), IFNULL(spl.attribute_value, "-"),
		IFNULL(tt.attribute_value, "-"), IFNULL(mtm.attribute_value, "-"),
		IFNULL(purpose.attribute_value, "-"), IFNULL(type.attribute_value, "-"),
		CAST(d1.attribute_value AS DECIMAL(8,3)), 
		CAST(w1.attribute_value AS DECIMAL(8,3)), 
		CAST(l1.attribute_value AS DECIMAL(8,3)), 
		CAST(d2.attribute_value AS DECIMAL(8,3)), 
		CAST(l2.attribute_value AS DECIMAL(8,3)),
		CAST(zn.attribute_value AS UNSIGNED),
		it.description,
		sum(if(bn.warehouse = "BGH655 - RIGPL" OR bn.warehouse = "DEL20A - RIGPL" OR bn.warehouse = "Dead Stock - RIGPL", 
			(bn.actual_qty), 0)),

		sum(if(bn.warehouse != "BGH655 - RIGPL" AND bn.warehouse != "DEL20A - RIGPL" 
			AND bn.warehouse != "REJ-DEL20A - RIGPL" AND bn.warehouse != "Dead Stock - RIGPL",
			(bn.actual_qty + bn.ordered_qty + bn.planned_qty), 0)),
			
		sum(if(bn.warehouse = "BGH655 - RIGPL" OR bn.warehouse = "DEL20A - RIGPL", 
			(bn.ordered_qty + bn.planned_qty), 0))

	FROM `tabItem` it
		LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent
		LEFT JOIN `tabBin` bn ON it.name = bn.item_code
		LEFT JOIN `tabItem Variant Attribute` rm ON it.name = rm.parent
			AND rm.attribute = 'Is RM'
		LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` brand ON it.name = brand.parent
			AND brand.attribute = 'Brand'
		LEFT JOIN `tabItem Variant Attribute` quality ON it.name = quality.parent
			AND quality.attribute = '%s Quality'
		LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
			AND tt.attribute = 'Tool Type'
		LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent
			AND spl.attribute = 'Special Treatment'
		LEFT JOIN `tabItem Variant Attribute` d1 ON it.name = d1.parent
			AND d1.attribute = 'd1_mm'
		LEFT JOIN `tabItem Variant Attribute` w1 ON it.name = w1.parent
			AND w1.attribute = 'w1_mm'
		LEFT JOIN `tabItem Variant Attribute` l1 ON it.name = l1.parent
			AND l1.attribute = 'l1_mm'
		LEFT JOIN `tabItem Variant Attribute` d2 ON it.name = d2.parent
			AND d2.attribute = 'd2_mm'
		LEFT JOIN `tabItem Variant Attribute` l2 ON it.name = l2.parent
			AND l2.attribute = 'l2_mm'
		LEFT JOIN `tabItem Variant Attribute` zn ON it.name = zn.parent
			AND zn.attribute = 'Number of Flutes Zn'
		LEFT JOIN `tabItem Variant Attribute` series ON it.name = series.parent
			AND series.attribute = 'Series'
		LEFT JOIN `tabItem Variant Attribute` mtm ON it.name = mtm.parent
			AND mtm.attribute = 'Material to Machine'
		LEFT JOIN `tabItem Variant Attribute` type ON it.name = type.parent
			AND type.attribute = 'Type Selector'
		LEFT JOIN `tabItem Variant Attribute` purpose ON it.name = purpose.parent
			AND purpose.attribute = 'Purpose'
	
	WHERE bn.item_code != ""
		AND rm.attribute_value is NULL
		AND bm.attribute_value IS NOT NULL
		AND bn.item_code = it.name
		AND ifnull(it.end_of_life, '2099-12-31') > CURDATE() %s

	GROUP BY bn.item_code
	
	ORDER BY
			rm.attribute_value, brand.attribute_value,
			spl.attribute_value, tt.attribute_value, 
			CAST(d1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(w1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(l1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(d2.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(l2.attribute_value AS DECIMAL(8,3)) ASC""" % (bm, conditions_it), as_list=1)
					
	return data
	
def get_conditions(filters):
	conditions_it = ""
		
	if filters.get("bm"):
		conditions_it += " AND bm.attribute_value = '%s'" % filters["bm"]

	if filters.get("series"):
		conditions_it += " AND series.attribute_value = '%s'" % filters["series"]
		
	if filters.get("tt"):
		conditions_it += " AND tt.attribute_value = '%s'" % filters["tt"]

	if filters.get("brand"):
		conditions_it += " AND brand.attribute_value = '%s'" % filters["brand"]

	if filters.get("quality"):
		conditions_it += " AND quality.attribute_value = '%s'" % filters["quality"]

	if filters.get("spl"):
		conditions_it += " AND spl.attribute_value = '%s'" % filters["spl"]

	if filters.get("item"):
		conditions_it += " and it.name = '%s'" % filters["item"]
	
	return conditions_it
