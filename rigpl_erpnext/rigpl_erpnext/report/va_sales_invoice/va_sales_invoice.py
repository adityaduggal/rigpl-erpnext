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
	conditions, params = get_conditions(filters)

	# 1. Base Query: Fetch SI and SID
	si_items = frappe.db.sql(f""" 
		SELECT 
			si.posting_date, si.name, si.customer,
			sid.item_code, sid.description, sid.qty, sid.base_price_list_rate, 
			sid.base_rate, sid.base_amount
		FROM `tabSales Invoice` si
		JOIN `tabSales Invoice Item` sid ON sid.parent = si.name
		JOIN `tabItem` it ON it.name = sid.item_code
		WHERE si.docstatus = 1 {conditions}
		ORDER BY si.posting_date ASC, si.name ASC, sid.item_code ASC, sid.description ASC
	""", params, as_dict=1)

	if not si_items:
		return []

	# Get unique item codes
	item_codes = list(set([d.item_code for d in si_items if d.item_code]))

	# 2. Bulk Fetch Attributes (O(1) mapping)
	attr_map = get_attribute_map(item_codes)

	res = []
	for row in si_items:
		attrs = attr_map.get(row.item_code, {})
		
		# Map attributes with fallback to "-"
		base_metal = attrs.get("Base Material", "-")
		tool_type = attrs.get("Tool Type", "-")
		hss_qual = attrs.get("HSS Quality", "-")
		car_qual = attrs.get("Carbide Quality", "-")
		spl = attrs.get("Special Treatment", "-")
		
		# Decimal conversions for dimensions
		d1 = flt(attrs.get("d1_mm")) if "d1_mm" in attrs else None
		w1 = flt(attrs.get("w1_mm")) if "w1_mm" in attrs else None
		l1 = flt(attrs.get("l1_mm")) if "l1_mm" in attrs else None
		d2 = flt(attrs.get("d2_mm")) if "d2_mm" in attrs else None
		l2 = flt(attrs.get("l2_mm")) if "l2_mm" in attrs else None

		res.append([
			row.posting_date, row.name, row.customer,
			row.item_code, row.description, row.qty, row.base_price_list_rate,
			row.base_rate, row.base_amount,
			base_metal, tool_type, hss_qual, car_qual,
			d1, w1, l1, d2, l2, spl
		])

	return res

def get_attribute_map(item_codes):
	if not item_codes: return {}
	
	attrs_to_fetch = [
		'Base Material', 'Tool Type', 'HSS Quality', 'Carbide Quality',
		'Special Treatment', 'd1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm'
	]
	
	# Fetch all attributes in one go
	raw_attrs = frappe.get_all("Item Variant Attribute",
		filters={"parent": ["in", item_codes], "attribute": ["in", attrs_to_fetch]},
		fields=["parent", "attribute", "attribute_value"]
	)
	
	res = {}
	for a in raw_attrs:
		res.setdefault(a.parent, {})[a.attribute] = a.attribute_value
	return res

def get_conditions(filters):
	conditions = ""
	params = {}
	
	if filters.get("from_date"):
		conditions += " AND si.posting_date >= %(from_date)s"
		params["from_date"] = filters["from_date"]
	else:
		frappe.msgprint("Please Select a From Date first", raise_exception=1)

	if filters.get("to_date"):
		conditions += " AND si.posting_date <= %(to_date)s"
		params["to_date"] = filters["to_date"]

	return conditions, params
