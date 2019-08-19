# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
	wh_dict = frappe.db.sql("""SELECT name, listing_serial, short_code, type_of_warehouse FROM `tabWarehouse` 
		WHERE disabled=0 AND is_group=0 AND listing_serial != 0  and is_subcontracting_warehouse = 0 
		ORDER BY listing_serial ASC""", as_dict=1)
	columns = get_columns(wh_dict)
	data = get_items(filters, wh_dict)
	return columns, data

def get_columns(wh_dict):
	columns = [
		"Item:Link/Item:80", 
		
		##Item Attribute fields
		"RM::30", "Brand::40", "Qual::50", "SPL::50", "TT::60",
		"D1:Float:40", "W1:Float:40", "L1:Float:50",
		"D2:Float:40", "L2:Float:40", "Zn:Float:40",
		###Item Attribute fields
		
		"CUT::120","URG::120",
		"Total:Float:50",
		"RO:Float:40", "SO:Float:40", "PO:Float:40",
		"PL:Float:40"
	]

	for wh in wh_dict:
		if wh.listing_serial < 10:
			columns += [wh.short_code + ":Float:50"]
	columns += ["Description::300"]
	for wh in wh_dict:
		if wh.listing_serial>=10:
			columns += [wh.short_code + ":Float:50"]

	columns += ["JW:Int:30", "Pur:Int:30", "Sale:Int:30"]

	return columns

def get_items(filters, wh_dict):
	actual_data = []
	wh_query = ""
	for wh in wh_dict:
		if wh.listing_serial < 10:
			wh_query += "IF(MIN(CASE WHEN bn.warehouse='%s' THEN bn.actual_qty END)=0,NULL,\
				MIN(CASE WHEN bn.warehouse='%s' THEN bn.actual_qty END)) as '%s',\
				"%(wh.name, wh.name, wh.short_code)
	wh_query += " it.description, "
	for wh in wh_dict:
		if wh.listing_serial >= 10:
			wh_query += "IF(MIN(CASE WHEN bn.warehouse='%s' THEN bn.actual_qty END)=0,NULL,\
				MIN(CASE WHEN bn.warehouse='%s' THEN bn.actual_qty END)) as '%s',\
				"%(wh.name, wh.name, wh.short_code)

	conditions_it = get_conditions(filters)
	bm = filters["bm"]
	query = """
	SELECT 
		it.name as name,
		IFNULL(rm.attribute_value, "-") as is_rm, IFNULL(brand.attribute_value, "-") as brand,
		IFNULL(quality.attribute_value, "-") as qual, IFNULL(spl.attribute_value, "-") as spl,
		IFNULL(tt.attribute_value, "-") as tool_type, 
		CAST(d1.attribute_value AS DECIMAL(8,3)) as d1, 
		CAST(w1.attribute_value AS DECIMAL(8,3)) as w1, 
		CAST(l1.attribute_value AS DECIMAL(8,3)) as l1, 
		CAST(d2.attribute_value AS DECIMAL(8,3)) as d2, 
		CAST(l2.attribute_value AS DECIMAL(8,3)) as l2,
		CAST(zn.attribute_value AS UNSIGNED) as zn,
		"CUT WIP" as cut_urg, "PRD WIP" as prd_urg, 0 as total,
		if(ro.warehouse_reorder_level=0, NULL ,ro.warehouse_reorder_level) as rol,
		if(sum(bn.reserved_qty)=0,NULL,sum(bn.reserved_qty)) as on_so,
		if(sum(bn.ordered_qty)=0,NULL,sum(bn.ordered_qty)) as on_po,
		if(sum(bn.planned_qty)=0,NULL,sum(bn.planned_qty)) as on_prd, %s
			
		it.is_job_work as jw, it.is_purchase_item as pur, it.is_sales_item as sale, it.valuation_rate as vr

	FROM `tabItem` it
		LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent
		LEFT JOIN `tabBin` bn ON it.name = bn.item_code
		LEFT JOIN `tabWarehouse` wh ON bn.warehouse = wh.name
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
	
	WHERE bn.item_code != ""
		AND bn.item_code = it.name
		AND ifnull(it.end_of_life, '2099-12-31') > CURDATE() %s

	GROUP BY bn.item_code
	
	ORDER BY rm.attribute_value, brand.attribute_value,
			spl.attribute_value, tt.attribute_value, 
			CAST(d1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(w1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(l1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(d2.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(l2.attribute_value AS DECIMAL(8,3)) ASC""" % (wh_query, bm, conditions_it)
	data = frappe.db.sql(query, as_dict=1)

	subcon = frappe.db.sql("""SELECT bn.item_code, bn.actual_qty FROM `tabBin` bn, `tabWarehouse` wh
		WHERE wh.is_subcontracting_warehouse = 1 AND bn.actual_qty > 0 
		AND wh.name = bn.warehouse""", as_dict = 1)

	for i in range(0,len(data)):
		ROL = flt(data[i].rol)
		SO = flt(data[i].on_so)
		PO = flt(data[i].on_po)
		PLAN = flt(data[i].on_prd)
		VR = flt(data[i].vr)
		stock = 0
		prd_qty = 0
		dead = 0
		urg = ""
		prd = ""

		for d in subcon:
			if d.item_code == data[i].name:
				PO += d.actual_qty

		if data[i].is_rm == 1:
			for wh in wh_dict:
				if wh.type_of_warehouse == "Raw Material":
					stock += flt(data[i].get(wh.short_code))
				elif wh.type_of_warehouse == "Finished Stock":
					stock += flt(data[i].get(wh.short_code))
				elif wh.type_of_warehouse == "Dead Stock":
					dead += flt(data[i].get(wh.short_code))
		else:
			for wh in wh_dict:
				if wh.type_of_warehouse == "Finished Stock":
					stock += flt(data[i].get(wh.short_code))
				elif wh.type_of_warehouse != "Finished Stock" and wh.type_of_warehouse != "Recoverable Stock":
					if wh.type_of_warehouse == "Dead Stock":
						dead += flt(data[i].get(wh.short_code))
					else:
						prd_qty += flt(data[i].get(wh.short_code))
		total = stock + prd_qty + PLAN + PO

		if 0 <= ROL*VR <= 1000:
			ROL = 5*ROL
		elif 1000 < ROL*VR <= 2000:
			ROL = 2.5*ROL
		elif 2000 < ROL*VR <= 5000:
			ROL = 1.5*ROL

		if dead > 0:
			urg = "Dead Stock"
		elif total < SO:
			urg = "1C ORD"
		elif total < SO + (0.3 * ROL):
			urg = "2C STK"
		elif total < SO + (0.6 * ROL):
			urg = "3C STK"
		elif total < SO + (1 * ROL):
			urg = "4C STK"
		elif total < SO + (1.4 * ROL):
			urg = "5C STK"
		elif total < SO + (1.8 * ROL):
			urg = "6C STK"
		elif total > (SO + 2.5 * ROL):
			if ROL > 0:
				urg = "7 Over"
			else:
				urg = ""
		else:
			urg = ""
		
		#Cutting Quantity
		if urg != "":
			c_qty = ((2 * ROL) + SO - total)
			urg = urg + " Qty= " + str(c_qty)

		if dead > 0:
			prd = "Dead Stock"
		elif stock < SO:
			prd = "1P ORD"
		elif stock < SO + ROL:
			prd = "2P STK"
		elif stock < SO + 1.2*ROL:
			prd = "3P STK"
		elif stock < SO + 1.4*ROL:
			prd = "4P STK"
		elif stock < SO + 1.6*ROL:
			prd = "5P STK"
		elif stock < SO + 1.8*ROL:
			prd = "6P STK"
		elif stock < SO + 2*ROL:
			prd = "7P STK"
		elif stock > SO + 2.5*ROL:
			if ROL >0:
				prd = "9 OVER"
			else:
				prd = ""
		else:
			prd = ""

		#Production Quantity
		if prd != "":
			shortage = (2 * ROL) - stock
			if shortage < prd_qty:
				prd = prd + " Qty= " + str(shortage)
			else:
				prd = prd + " Qty = " + str(prd_qty)
		row = [data[i].name, data[i].is_rm, data[i].brand, data[i].qual, data[i].spl, data[i].tool_type, data[i].d1, \
			data[i].w1, data[i].l1, data[i].d2, data[i].l2, data[i].zn, urg, prd, \
			total, data[i].rol, data[i].on_so, PO, data[i].on_prd]
		for wh in wh_dict:
			if wh.listing_serial < 10:
				row += [data[i].get(wh.short_code)]
		row += [data[i].description]
		for wh in wh_dict:
			if wh.listing_serial >= 10:
				row += [data[i].get(wh.short_code)]
		row += [data[i].jw, data[i].pur, data[i].sale]
		actual_data.append(row)
	return actual_data

def get_conditions(filters):
	conditions_it = ""

	if filters.get("rm"):
		conditions_it += " AND rm.attribute_value = '%s'" % filters["rm"]
		
	if filters.get("bm"):
		conditions_it += " AND bm.attribute_value = '%s'" % filters["bm"]

	if filters.get("brand"):
		conditions_it += " AND brand.attribute_value = '%s'" % filters["brand"]

	if filters.get("quality"):
		conditions_it += " AND quality.attribute_value = '%s'" % filters["quality"]

	if filters.get("spl"):
		conditions_it += " AND spl.attribute_value = '%s'" % filters["spl"]
		
	if filters.get("tt"):
		conditions_it += " AND tt.attribute_value = '%s'" % filters["tt"]


	if filters.get("show_in_website") ==1:
		conditions_it += " and it.show_in_website =%s" % filters["show_in_website"]

	if filters.get("item"):
		conditions_it += " and it.name = '%s'" % filters["item"]
	
	if filters.get("variant_of"):
		conditions_it += " and it.variant_of = '%s'" % filters["variant_of"]

	return conditions_it