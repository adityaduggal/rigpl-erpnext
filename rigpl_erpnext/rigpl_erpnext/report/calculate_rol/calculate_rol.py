from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_sl_entries(filters)

	return columns, data

def get_columns():
	return [
		"Item:Link/Item:130", "ROL:Int:60", "SOLD:Int:60",
		"#Cust:Int:60", "CON:Int:60", "SI Avg:Int:60", "CON Avg:Int:60",
		"TotA:Int:80", "Diff:Int:60","BM::60", "Brand::60",
		"Quality::80", "TT::150", "SPL::60", 
		"D1 MM:Float:60", "W1 MM:Float:60", "L1 MM:Float:60", 
		"D2 MM:Float:60","L2 MM:Float:60",
		"Description::450"
	]

def get_sl_entries(filters):
	conditions_it = get_conditions(filters)[0]
	conditions_so = get_conditions(filters)[1]
	conditions_sle = get_conditions(filters)[2]
	bm = frappe.db.get_value("Item Attribute Value", filters["bm"], "attribute_value")

	if (filters.get("from_date")):
		diff = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days
		if diff < 0:
			frappe.msgprint ("From date has to be less than To Date", raise_exception=1)
	else:
		frappe.msgprint ("Please select from date first", raise_exception=1)

	pre_data = frappe.db.sql("""SELECT it.name FROM `tabItem` it
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
		
		WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE() 
		%s""" % (bm, conditions_it))
	
	if len(pre_data) > 1000:
		frappe.throw(("Server overload possible due to {0} rows of data, kindly reduce \
			the lines by selecting filters").format(len(pre_data)))
	
	query = """SELECT it.name, IF(it.re_order_level=0,NULL,it.re_order_level),
		
		(SELECT (SUM(sle.actual_qty)*-1)
			FROM `tabStock Ledger Entry` sle WHERE sle.voucher_type IN 
			('Delivery Note', 'Sales Invoice') AND sle.is_cancelled = "No" 
			AND sle.item_code = it.name %s), 
		
		(SELECT COUNT(DISTINCT(so.customer))
			FROM `tabSales Order` so, `tabSales Order Item` sod
			WHERE sod.parent = so.name 
			AND so.docstatus = 1 
			AND sod.item_code = it.name %s
			GROUP BY sod.item_code), 
		
		null,null, null,null, null, 
		
		IFNULL(bm.attribute_value, "-"), IFNULL(brand.attribute_value, "-"), 
		IFNULL(quality.attribute_value, "-"),
		IFNULL(tt.attribute_value, "-"), IFNULL(spl.attribute_value, "-"), 
		CAST(d1.attribute_value AS DECIMAL(8,3)), 
		CAST(w1.attribute_value AS DECIMAL(8,3)), 
		CAST(l1.attribute_value AS DECIMAL(8,3)), 
		CAST(d2.attribute_value AS DECIMAL(8,3)), 
		CAST(l2.attribute_value AS DECIMAL(8,3)), it.description
		
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
		
		
		WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE() 
		%s""" % (conditions_sle, conditions_so, bm,conditions_it)

	data = frappe.db.sql(query, as_list=1)


	return data

def get_conditions(filters):
	conditions_it = ""
	conditions_so = ""
	conditions_sle = ""

	if filters.get("item"):
		conditions_it += " AND it.name = '%s'" % filters["item"]

	if filters.get("is_rm"):
		rm = frappe.db.get_value("Item Attribute Value", filters["is_rm"], "attribute_value")
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

	if filters.get("from_date"):
		conditions_so += " AND so.transaction_date >= '%s'" % filters["from_date"]
		conditions_sle += " AND sle.posting_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions_so += " AND so.transaction_date <= '%s'" % filters["to_date"]
		conditions_sle += " AND sle.posting_date <= '%s'" % filters["to_date"]
		
	return conditions_it, conditions_so, conditions_sle

