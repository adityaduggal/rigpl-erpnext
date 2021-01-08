# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_sl_entries(filters)

	return columns, data


def get_columns():
	return [
		"Item:Link/Item:130", "ROL:Int:50", "SOLD:Int:50",
		"#Cust:Int:50", "CON:Int:50", "CON SR:Int:60", "SI Avg:Int:50",
		"CON Avg:Int:50", "TotA:Int:50", "Diff:Int:40", "# SO:Int:40",
		"BM::60", "Brand::60", "Quality::60", "TT::130", "SPL::50",
		"D1 MM:Float:50", "W1 MM:Float:50", "L1 MM:Float:60",
		"D2 MM:Float:50", "L2 MM:Float:60",
		"Description::450", "Template:Link/Item:150"
	]


def get_sl_entries(filters):
	conditions_it, conditions_so, conditions_sle, conditions_ste, conditions_sr = \
		get_conditions(filters)
	bm = filters.get("bm")

	if filters.get("from_date"):
		diff = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days
		if diff < 0:
			frappe.msgprint("From date has to be less than To Date", raise_exception=1)
	else:
		frappe.msgprint("Please select from date first", raise_exception=1)

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

	if len(pre_data) > 1500:
		frappe.throw(("Server overload possible due to {0} rows of data, kindly reduce \
			the lines by selecting filters").format(len(pre_data)))

	query = """SELECT it.name, IF(ro.warehouse_reorder_level=0,NULL,ro.warehouse_reorder_level),

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

		(SELECT SUM(sted.qty) FROM `tabStock Entry Detail` sted,
			`tabStock Entry` ste
			WHERE sted.parent = ste.name AND ste.docstatus = 1 
			AND sted.s_warehouse IS NOT NULL
			AND (sted.t_warehouse IS NULL OR sted.t_warehouse = "")
			AND sted.item_code = it.name %s),

		(SELECT SUM(srd.current_qty - srd.qty) 
			FROM `tabStock Reconciliation` sr, `tabStock Reconciliation Item` srd

			WHERE 
			srd.parent = sr.name AND sr.docstatus = 1 
			AND srd.qty != srd.current_qty
			AND srd.current_valuation_rate = srd.valuation_rate
			AND srd.item_code = it.name
			AND sr.posting_time != '23:59:59' %s),

		null, null,null, null, 

		IF((SELECT COUNT(DISTINCT(so.name)) FROM `tabSales Order` so,
			`tabSales Order Item` sod WHERE so.name = sod.parent
			AND sod.item_code = it.name AND so.docstatus = 1 %s)=0, NULL,
			(SELECT COUNT(DISTINCT(so.name)) FROM `tabSales Order` so,
			`tabSales Order Item` sod WHERE so.name = sod.parent
			AND sod.item_code = it.name AND so.docstatus = 1 %s)),

		IFNULL(bm.attribute_value, "-"), IFNULL(brand.attribute_value, "-"), 
		IFNULL(quality.attribute_value, "-"),
		IFNULL(tt.attribute_value, "-"), IFNULL(spl.attribute_value, "-"), 
		CAST(d1.attribute_value AS DECIMAL(8,3)), 
		CAST(w1.attribute_value AS DECIMAL(8,3)), 
		CAST(l1.attribute_value AS DECIMAL(8,3)), 
		CAST(d2.attribute_value AS DECIMAL(8,3)), 
		CAST(l2.attribute_value AS DECIMAL(8,3)), it.description, it.variant_of

		FROM `tabItem` it
		LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent
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
		LEFT JOIN `tabItem Variant Attribute` purpose ON it.name = purpose.parent
			AND purpose.attribute = 'Purpose'
		LEFT JOIN `tabItem Variant Attribute` type ON it.name = type.parent
			AND type.attribute = 'Type Selector'
		LEFT JOIN `tabItem Variant Attribute` mtm ON it.name = mtm.parent
			AND mtm.attribute = 'Material to Machine'
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
			IFNULL(it.end_of_life, '2099-12-31') > CURDATE() %s
		ORDER BY 
			bm.attribute_value, quality.attribute_value, 
			tt.attribute_value, CAST(d1.attribute_value AS DECIMAL(8,3)),
			CAST(w1.attribute_value AS DECIMAL(8,3)),
			CAST(d2.attribute_value AS DECIMAL(8,3)),
			CAST(l2.attribute_value AS DECIMAL(8,3))""" % (conditions_sle, conditions_so, conditions_ste,
														   conditions_sr, conditions_so, conditions_so, bm,
														   conditions_it)

	data = frappe.db.sql(query, as_list=1)

	diff = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days
	if diff < 0:
		frappe.throw("From date should be before To Date")

	for i in range(len(data)):
		sold = None
		cons = None
		si_avg = None
		tot_avg = None
		con_avg = None
		change = None
		rol = None

		rol = flt(data[i][1])
		sold = flt(data[i][2])
		cons = flt(data[i][4])
		sr = flt(data[i][5])
		if sold:
			si_avg = (sold / diff) * 30
		if cons or sr:
			con_avg = ((cons + sr) / diff) * 30
		if si_avg:
			if con_avg:
				tot_avg = con_avg + si_avg
			else:
				tot_avg = si_avg
		else:
			if con_avg:
				tot_avg = con_avg
			else:
				tot_avg = None

		if rol:
			if tot_avg:
				change = tot_avg - rol
			else:
				change = -rol
		else:
			if tot_avg:
				change = tot_avg
			else:
				change = None

		data[i][6] = si_avg
		data[i][7] = con_avg
		data[i][8] = tot_avg
		data[i][9] = change

	return data


def get_conditions(filters):
	conditions_it = ""
	conditions_so = ""
	conditions_sle = ""
	conditions_ste = ""
	conditions_sr = ""

	if filters.get("item"):
		conditions_it += " AND it.name = '%s'" % filters.get("item")

	if filters.get("rm"):
		conditions_it += " AND rm.attribute_value = '%s'" % filters.get("rm")

	if filters.get("bm"):
		conditions_it += " AND bm.attribute_value = '%s'" % filters.get("bm")

	if filters.get("brand"):
		conditions_it += " AND brand.attribute_value = '%s'" % filters.get("brand")

	if filters.get("quality"):
		conditions_it += " AND quality.attribute_value = '%s'" % filters.get("quality")

	if filters.get("spl"):
		conditions_it += " AND spl.attribute_value = '%s'" % filters.get("spl")

	if filters.get("purpose"):
		conditions_it += " AND purpose.attribute_value = '%s'" % filters.get("purpose")

	if filters.get("type"):
		conditions_it += " AND type.attribute_value = '%s'" % filters.get("type")

	if filters.get("mtm"):
		conditions_it += " AND mtm.attribute_value = '%s'" % filters.get("mtm")

	if filters.get("tt"):
		conditions_it += " AND tt.attribute_value = '%s'" % filters.get("tt")

	if filters.get("from_date"):
		conditions_so += " AND so.transaction_date >= '%s'" % filters.get("from_date")
		conditions_sle += " AND sle.posting_date >= '%s'" % filters.get("from_date")
		conditions_ste += " AND ste.posting_date >= '%s'" % filters.get("from_date")
		conditions_sr += " AND sr.posting_date >= '%s'" % filters.get("from_date")

	if filters.get("to_date"):
		conditions_so += " AND so.transaction_date <= '%s'" % filters.get("to_date")
		conditions_sle += " AND sle.posting_date <= '%s'" % filters.get("to_date")
		conditions_ste += " AND ste.posting_date <= '%s'" % filters.get("to_date")
		conditions_sr += " AND sr.posting_date <= '%s'" % filters.get("to_date")

	return conditions_it, conditions_so, conditions_sle, conditions_ste, conditions_sr