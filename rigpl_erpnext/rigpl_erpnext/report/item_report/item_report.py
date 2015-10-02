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
		"Item:Link/Item:130", "RM::30", "BM::60","Brand::50","Quality::70", "SPL::50", 
		"TT::150", "MTM::60", "Purpose::60", "Type::60",
		"D1:Float:50","W1:Float:50", "L1:Float:60", 
		"D2:Float:50", "L2:Float:50", "Zn:Int:30",
		"D3:Float:50", "L3:Float:50", "A1_DEG:Float:50",
		"D1_Inch::50", "W1_Inch::50", "L1_Inch::50",
		"CETSH::70", "Template or Variant Of:Link/Item:300", "Description::400",
		"EOL:Date:100", "Created By:Link/User:150", "Creation:Date:150"
	]

def get_items(filters):
	conditions_it = get_conditions(filters)
	bm = frappe.db.get_value("Item Attribute Value", filters["bm"], "attribute_value")

	query = """SELECT it.name, 
		IFNULL(rm.attribute_value, "-"), IFNULL(bm.attribute_value, "-"),
		IFNULL(brand.attribute_value, "-"), IFNULL(quality.attribute_value, "-"),
		IFNULL(spl.attribute_value, "-"), IFNULL(tt.attribute_value, "-"),
		IFNULL(mtm.attribute_value, "-"), IFNULL(purpose.attribute_value, "-"),
		IFNULL(type.attribute_value, "-"), 
		CAST(d1.attribute_value AS DECIMAL(8,3)), 
		CAST(w1.attribute_value AS DECIMAL(8,3)), 
		CAST(l1.attribute_value AS DECIMAL(8,3)), 
		CAST(d2.attribute_value AS DECIMAL(8,3)), 
		CAST(l2.attribute_value AS DECIMAL(8,3)),
		CAST(zn.attribute_value AS UNSIGNED),
		CAST(d3.attribute_value AS DECIMAL(8,3)), 
		CAST(l3.attribute_value AS DECIMAL(8,3)),
		CAST(a1.attribute_value AS DECIMAL(8,3)), 
		IFNULL(d1_inch.attribute_value, "-"),
		IFNULL(w1_inch.attribute_value, "-"),
		IFNULL(l1_inch.attribute_value, "-"),
		IFNULL(cetsh.attribute_value, "-"), it.variant_of, 
		it.description, IFNULL(it.end_of_life, '2099-12-31'), 
		it.owner, it.creation
		
		FROM `tabItem` it
		
		LEFT JOIN `tabItem Variant Attribute` rm ON it.name = rm.parent
			AND rm.attribute = 'Is RM'
		LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` quality ON it.name = quality.parent
			AND quality.attribute = '%s Quality'
		LEFT JOIN `tabItem Variant Attribute` brand ON it.name = brand.parent
			AND brand.attribute = 'Brand'
		LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
			AND tt.attribute = 'Tool Type'
		LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent
			AND spl.attribute = 'Special Treatment'
		LEFT JOIN `tabItem Variant Attribute` mtm ON it.name = mtm.parent
			AND mtm.attribute = 'Material to Machine'
		LEFT JOIN `tabItem Variant Attribute` type ON it.name = type.parent
			AND type.attribute = 'Type Selector'
		LEFT JOIN `tabItem Variant Attribute` purpose ON it.name = purpose.parent
			AND purpose.attribute = 'Purpose'
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
			AND zn.attribute = 'Number of Flutes (Zn)'
		LEFT JOIN `tabItem Variant Attribute` d3 ON it.name = d3.parent
			AND d3.attribute = 'd3_mm'
		LEFT JOIN `tabItem Variant Attribute` l3 ON it.name = l3.parent
			AND l3.attribute = 'l3_mm'
		LEFT JOIN `tabItem Variant Attribute` a1 ON it.name = a1.parent
			AND a1.attribute = 'a1_deg'
		LEFT JOIN `tabItem Variant Attribute` d1_inch ON it.name = d1_inch.parent
			AND d1_inch.attribute = 'd1_inch'
		LEFT JOIN `tabItem Variant Attribute` w1_inch ON it.name = w1_inch.parent
			AND w1_inch.attribute = 'w1_inch'
		LEFT JOIN `tabItem Variant Attribute` l1_inch ON it.name = l1_inch.parent
			AND l1_inch.attribute = 'l1_inch'
		LEFT JOIN `tabItem Variant Attribute` cetsh ON it.name = cetsh.parent
			AND cetsh.attribute = 'CETSH Number' %s
		
		ORDER BY rm.attribute_value, bm.attribute_value, brand.attribute_value,
			quality.attribute_value, spl.attribute_value, tt.attribute_value, 
			CAST(d1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(w1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(l1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(d2.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(l2.attribute_value AS DECIMAL(8,3)) ASC,
			CAST(d3.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(l3.attribute_value AS DECIMAL(8,3)) ASC""" % (bm, conditions_it)
	

	data = frappe.db.sql(query, as_list=1)
	
	attributes = ['Is RM', 'Base Material', 'Brand', '%Quality', 'Special Treatment',
		'Tool Type', 'Material to Machine', 'Purpose', 'Type Selector',
		'd1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm', 'd3_mm', 'l3_mm',
		'a1_deg',
		'd1_inch', 'w1_inch', 'l1_inch',
		'CETSH Number',]
	
	float_fields = ['d1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm', 
		'd3_mm', 'l3_mm', 'a1_deg']

	return data

def get_conditions(filters):
	conditions_it = ""

	if filters.get("eol"):
		conditions_it += "WHERE IFNULL(it.end_of_life, '2099-12-31') > '%s'" % filters["eol"]
	
	if filters.get("rm"):
		rm = frappe.db.get_value("Item Attribute Value", filters["rm"], "attribute_value")
		conditions_it += " AND rm.attribute_value = '%s'" % rm

	if filters.get("bm"):
		bm = frappe.db.get_value("Item Attribute Value", filters["bm"], "attribute_value")
		conditions_it += " AND bm.attribute_value = '%s'" % bm

	if filters.get("brand"):
		brand = frappe.db.get_value("Item Attribute Value", filters["brand"], "attribute_value")
		conditions_it += " AND brand.attribute_value = '%s'" % brand

	if filters.get("quality"):
		quality = frappe.db.get_value("Item Attribute Value", filters["quality"], "attribute_value")
		conditions_it += " AND quality.attribute_value = '%s'" % quality

	if filters.get("spl"):
		spl = frappe.db.get_value("Item Attribute Value", filters["spl"], "attribute_value")
		conditions_it += " AND spl.attribute_value = '%s'" % spl
		
	if filters.get("tt"):
		tt = frappe.db.get_value("Item Attribute Value", filters["tt"], "attribute_value")
		conditions_it += " AND tt.attribute_value = '%s'" % tt


	if filters.get("show_in_website") ==1:
		conditions_it += " and it.show_in_website =%s" % filters["show_in_website"]

	if filters.get("item"):
		conditions_it += " and it.name = '%s'" % filters["item"]
	
	if filters.get("variant_of"):
		conditions_it += " and it.variant_of = '%s'" % filters["variant_of"]

	return conditions_it
