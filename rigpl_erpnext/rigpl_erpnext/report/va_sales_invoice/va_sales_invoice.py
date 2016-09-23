from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_va_entries(filters)

	return columns, data

def get_columns():

	return [
		"Posting Date:Date:80", "Name:Link/Sales Invoice:150" ,"Customer:Link/Customer:250",
		"Item Code:Link/Item:150","Description::350", "Quantity:Float:60",
		"List Price:Float/2:60", "Rate*:Currency:60", "Amount*:Currency:90",
		"Base Metal::100", "Tool Type::100", "HSS Qual::100", "Carb Qual::100",
		"D1 (mm):Float:60", "W1 (mm):Float:60", "L1 (mm):Float:60",
		"D2:Float:60", "L2:Float:60", "Special Treatment::80",
	]

def get_va_entries(filters):
	conditions = get_conditions(filters)

	si = frappe.db.sql(""" SELECT 
			si.posting_date, si.name, si.customer,
			sid.item_code, sid.description, sid.qty, sid.base_price_list_rate, 
			sid.base_rate, sid.base_amount, 
			IFNULL(bm.attribute_value, "-"),
			IFNULL(tt.attribute_value, "-"),
			IFNULL(hss_qual.attribute_value, "-"),
			IFNULL(car_qual.attribute_value, "-"),
			CAST(d1.attribute_value AS DECIMAL(8,3)), 
			CAST(w1.attribute_value AS DECIMAL(8,3)), 
			CAST(l1.attribute_value AS DECIMAL(8,3)), 
			CAST(d2.attribute_value AS DECIMAL(8,3)), 
			CAST(l2.attribute_value AS DECIMAL(8,3)),
			IFNULL(spl.attribute_value, "-")
			
		FROM `tabSales Invoice` si, `tabSales Invoice Item` sid, `tabItem` it
			LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
				AND bm.attribute = 'Base Material'
			LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
				AND tt.attribute = 'Tool Type'
			LEFT JOIN `tabItem Variant Attribute` hss_qual ON it.name = hss_qual.parent
				AND hss_qual.attribute = 'HSS Quality'
			LEFT JOIN `tabItem Variant Attribute` car_qual ON it.name = car_qual.parent
				AND car_qual.attribute = 'Carbide Quality'
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
		WHERE
			si.docstatus = 1 AND
			sid.parent = si.name AND
			si.docstatus = 1 AND it.name = sid.item_code %s
		ORDER BY si.posting_date ASC, si.name ASC, sid.item_code ASC,
			sid.description ASC""" % conditions, as_list=1)



	return si

def get_conditions(filters):
	conditions = ""
	if filters.get("from_date"):
		conditions += "and si.posting_date >= '%s'" % filters["from_date"]
	else:
		frappe.msgprint("Please Select a From Date first", raise_exception=1)

	if filters.get("to_date"):
		conditions += "and si.posting_date <= '%s'" % filters["to_date"]

	return conditions
