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
		"Item:Link/Item:130", 
		
		###Below are attribute fields
		"RM::30", "Brand::60", "Qual::80", "SPL::50", "TT::120",
		"D1:Float:50", "W1:Float:50", "L1:Float:50",
		###Above are Attribute fields
		"Future Stock::100", "Current Stock::100",
		"Total:Float:50",
		"RO:Float:40", "SO:Float:40", "PO:Float:40",
		"PL:Float:40", "IND:Float:50", "PRD:Float:50",
		"Description::300",
		"BRM:Float:50", "DRM:Float:50", "BGH:Float:50", "DEL:Float:50",
		"Dead:Float:50",
	]

def get_items(filters):
	actual_data = []
	conditions_it = get_conditions(filters)
	bm = filters["bm"]
	data = frappe.db.sql("""
	SELECT 
		it.name,
		IFNULL(rm.attribute_value, "-") AS rm, IFNULL(brand.attribute_value, "-") AS brand,
		IFNULL(quality.attribute_value, "-") AS qual, IFNULL(spl.attribute_value, "-") AS spl,
		IFNULL(tt.attribute_value, "-") AS tt, 
		CAST(d1.attribute_value AS DECIMAL(8,3)) AS d1, 
		CAST(w1.attribute_value AS DECIMAL(8,3)) AS w1, 
		CAST(l1.attribute_value AS DECIMAL(8,3)) AS l1, 
		if(ro.warehouse_reorder_level=0, NULL ,ro.warehouse_reorder_level) AS rol,
		if(sum(bn.reserved_qty)=0,NULL,sum(bn.reserved_qty)) AS so,
		if(sum(bn.ordered_qty)=0,NULL,sum(bn.ordered_qty)) AS po,
		if(sum(bn.planned_qty)=0,NULL,sum(bn.planned_qty)) AS plan,
		if(sum(bn.indented_qty)=0,NULL,sum(bn.indented_qty)) AS indent,
		if(sum(bn.reserved_qty_for_production)=0,NULL,sum(bn.reserved_qty_for_production)) AS prd,

		it.description,	
		
		if(min(case WHEN bn.warehouse="RM-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="RM-BGH655 - RIGPL" THEN bn.actual_qty end)) AS brm,

		if(min(case WHEN bn.warehouse="RM-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="RM-DEL20A - RIGPL" THEN bn.actual_qty end)) AS drm,

		if(min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)) AS bgh,

		if(min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)) AS del20a,

		if(min(case WHEN bn.warehouse="Dead Stock - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="Dead Stock - RIGPL" THEN bn.actual_qty end)) AS dead

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
	
	WHERE bn.item_code != ""
		AND it.is_purchase_item = 1
		AND it.has_variants = 0
		AND bn.item_code = it.name
		AND it.disabled = 0
		AND ifnull(it.end_of_life, '2099-12-31') > CURDATE() %s

	GROUP BY bn.item_code
	
	ORDER BY rm.attribute_value, brand.attribute_value,
			spl.attribute_value, tt.attribute_value, 
			CAST(d1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(w1.attribute_value AS DECIMAL(8,3)) ASC, 
			CAST(l1.attribute_value AS DECIMAL(8,3)) ASC""" % (bm, conditions_it), as_dict=1)
	for i in range(0, len(data)):
		rol = flt(data[i].rol)
		so = flt(data[i].so)
		po = flt(data[i].po)
		plan = flt(data[i].plan)
		ind = flt(data[i].indent)
		prd = flt(data[i].prd)
		brm = flt(data[i].brm)
		drm = flt(data[i].drm)
		bgh = flt(data[i].bgh)
		del20a = flt(data[i].del20a)
		dead = flt(data[i].dead)

		total = (drm + brm + plan + po + ind + bgh + del20a + dead) - prd

		stock = drm + brm + bgh + del20a + dead - prd
		prod = total - stock
		fut_stock = "X"

		if rol < 10:
			calc_rol = 3*rol
		elif 10 <= rol < 20:
			calc_rol = 2*rol
		elif 20 <= rol < 50:
			calc_rol = 1.5*rol
		else:
			calc_rol = rol

		if total < so:
			fut_stock = "Raise More PO and Indent"
		elif total < so + calc_rol:
			fut_stock = "1<30 Days"
		elif total < so + 2*calc_rol:
			fut_stock = "2<60 Days"
		elif total < so + 3*calc_rol:
			fut_stock = "3<90 Days"
		elif total < so + 4*calc_rol:
			fut_stock = "4<120 Days"
		elif total < so + 5*calc_rol:
			fut_stock = "5<150 Days"
		elif total < so + 6*calc_rol:
			fut_stock = "6<180 Days"
		elif total > so + 6*calc_rol:
			if rol >0:
				fut_stock = "7 Over Stocked >180 Days"
			else:
				fut_stock = "-"
		else:
			fut_stock = "-"
			
		if stock < calc_rol:
			cur_stock = "NO STOCK"
		elif stock < so + calc_rol:
			cur_stock = "1<30 Days"
		elif stock < so + 2*calc_rol:
			cur_stock = "2<60 Days"
		elif stock < so + 3*calc_rol:
			cur_stock = "3<90 Days"
		elif stock < so + 4*calc_rol:
			cur_stock = "4<120 Days"
		elif stock < so + 5*calc_rol:
			cur_stock = "5<150 Days"
		elif stock < so + 6*calc_rol:
			cur_stock = "6<180 Days"
		elif stock > so + 6*calc_rol:
			if rol >0:
				cur_stock = "7 Over Stocked >180 Days"
			else:
				cur_stock = "-"
		else:
			cur_stock = "-"

		row = [
			data[i].name, data[i].rm, data[i].brand, data[i].qual, data[i].spl, data[i].tt, data[i].d1,
			data[i].w1, data[i].l1, fut_stock, cur_stock, total, rol, so, po, plan, ind, prd, data[i].description,
			brm, drm, bgh, del20a, dead
		]
		for i in range(0, len(row)):
			if row[i] == 0:
				row[i] = None
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

