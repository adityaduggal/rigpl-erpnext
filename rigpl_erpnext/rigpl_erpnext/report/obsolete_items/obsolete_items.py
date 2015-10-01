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
		"VR:Link/Valuation Rate:100",
		"Created By:Link/User:150", "Creation:Date:130"
	]

def get_items(filters):
	conditions = get_conditions(filters)[0]
	tab_join = get_conditions(filters)[1]
	cond_join = get_conditions(filters)[2]

	pre_data = frappe.db.sql("""SELECT it.name FROM `tabItem` it %s %s %s""" 
		% (tab_join, conditions, cond_join), as_list = 1)
	
	if len(pre_data) > 500:
		frappe.throw(("Server overload possible due to {0} rows of data, kindly reduce \
			the lines by selecting filters").format(len(pre_data)))
	
	query = """SELECT it.name, it.description, it.pl_item, 
		it.is_sales_item, it.is_purchase_item, it.show_in_website, 
		it.stock_maintained, 
		
		ifnull((SELECT count(sod.name) FROM `tabSales Order Item` sod 
			WHERE sod.item_code = it.name GROUP BY sod.item_code),0),
		
		ifnull((SELECT count(sod.name) FROM `tabSales Invoice Item` sod 
			WHERE sod.item_code = it.name GROUP BY sod.item_code),0),
		
		ifnull((SELECT count(sod.name) FROM `tabPurchase Order Item` sod 
			WHERE sod.item_code = it.name GROUP BY sod.item_code),0),
		
		ifnull((SELECT count(sod.name) FROM `tabPurchase Invoice Item` sod 
			WHERE sod.item_code = it.name GROUP BY sod.item_code),0),
		
		ifnull((SELECT count(sod.name) FROM `tabStock Ledger Entry` sod 
			WHERE sod.item_code = it.name GROUP BY sod.item_code),0),
		
		ifnull((SELECT count(sod.name) FROM `tabStock Entry Detail` sod 
			WHERE sod.item_code = it.name GROUP BY sod.item_code),0),
		
		ifnull((SELECT count(sod.name) FROM `tabStock Reconciliation Item` sod 
			WHERE sod.item_code = it.name GROUP BY sod.item_code),0),
		
		ifnull((SELECT count(sod.name) FROM `tabProduction Order` sod 
			WHERE sod.production_item = it.name GROUP BY sod.production_item),0),
		
		(SELECT vr.name FROM `tabValuation Rate` vr WHERE vr.item_code = it.name),
		
		ifnull(it.owner,'Administrator'), it.creation 
		FROM `tabItem` it %s %s %s""" % (tab_join, conditions, cond_join)
	
	data = frappe.db.sql(query, as_list = 1)
	
	return data
	
def get_conditions(filters):
	conditions = ""
	tab_join = ""
	cond_join = ""
	
	if filters.get("eol"):
		conditions += "WHERE ifnull(it.end_of_life, '2099-12-31') > '%s'" % filters["eol"]

	if filters.get("is_pl_item"):
		conditions += " AND it.pl_item ='Yes'"
	else:
		conditions += " AND it.pl_item ='No'"
		
	if filters.get("has_variants"):
		conditions += " AND it.has_variants = 1"
	else:
		conditions += " AND it.has_variants = 0"
		
	if filters.get("item"):
		conditions += " AND it.name = '%s'" %filters["item"]

	if filters.get("bm"):
		bm = frappe.db.get_value("Item Attribute Value", filters["bm"], "attribute_value")
		tab_join += " LEFT JOIN `tabItem Variant Attribute` bm \
			ON it.name = bm.parent \
			AND bm.attribute = 'Base Material'"
		
		cond_join += " AND bm.attribute_value = '%s'" % bm
		
	if filters.get("is_rm"):
		rm = frappe.db.get_value("Item Attribute Value", filters["is_rm"], "attribute_value")
		tab_join += " LEFT JOIN `tabItem Variant Attribute` rm \
			ON it.name = rm.parent \
			AND rm.attribute = 'Is RM'"
		
		cond_join += " AND bm.attribute_value = '%s'" % rm
		
	if filters.get("brand"):
		brand = frappe.db.get_value("Item Attribute Value", filters["brand"], "attribute_value")
		tab_join += " LEFT JOIN `tabItem Variant Attribute` brand \
			ON it.name = brand.parent \
			AND brand.attribute = 'Brand'"
		
		cond_join += " AND brand.attribute_value = '%s'" % brand

	if filters.get("quality"):
		quality = frappe.db.get_value("Item Attribute Value", filters["quality"], "attribute_value")
		tab_join += " LEFT JOIN `tabItem Variant Attribute` quality \
			ON it.name = quality.parent \
			AND quality.attribute LIKE '%Quality'"
		
		cond_join += " AND quality.attribute_value = '%s'" % quality
		
	if filters.get("spl"):
		spl = frappe.db.get_value("Item Attribute Value", filters["spl"], "attribute_value")
		tab_join += " LEFT JOIN `tabItem Variant Attribute` spl \
			ON it.name = spl.parent \
			AND spl.attribute = 'Special Treatment'"
		
		cond_join += " AND spl.attribute_value = '%s'" % spl
		
	if filters.get("tt"):
		tt = frappe.db.get_value("Item Attribute Value", filters["tt"], "attribute_value")
		tab_join += " LEFT JOIN `tabItem Variant Attribute` tt \
			ON it.name = tt.parent \
			AND tt.attribute = 'Tool Type'"
		
		cond_join += " AND tt.attribute_value = '%s'" % tt
		
	return conditions, tab_join, cond_join