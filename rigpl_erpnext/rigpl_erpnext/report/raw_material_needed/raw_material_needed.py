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
		"PL:Float:40", "IND:Float:40",
		"Description::300",
		"BRM:Float:50", "DRM:Float:50", "BGH:Float:50", "DEL:Float:50",
		"Dead:Float:50",
	]

def get_items(filters):
	conditions_it = get_conditions(filters)
	bm = filters["bm"]
	data = frappe.db.sql("""
	SELECT 
		it.name,
		IFNULL(rm.attribute_value, "-"), IFNULL(brand.attribute_value, "-"),
		IFNULL(quality.attribute_value, "-"), IFNULL(spl.attribute_value, "-"),
		IFNULL(tt.attribute_value, "-"), 
		CAST(d1.attribute_value AS DECIMAL(8,3)), 
		CAST(w1.attribute_value AS DECIMAL(8,3)), 
		CAST(l1.attribute_value AS DECIMAL(8,3)), 
		if(ro.warehouse_reorder_level=0, NULL ,ro.warehouse_reorder_level),
		if(sum(bn.reserved_qty)=0,NULL,sum(bn.reserved_qty)),
		if(sum(bn.ordered_qty)=0,NULL,sum(bn.ordered_qty)),
		if(sum(bn.planned_qty)=0,NULL,sum(bn.planned_qty)),
		if(sum(bn.indented_qty)=0,NULL,sum(bn.indented_qty)),

		it.description,	
		
		if(min(case WHEN bn.warehouse="RM-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="RM-BGH655 - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="RM-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="RM-DEL20A - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="Dead Stock - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="Dead Stock - RIGPL" THEN bn.actual_qty end))

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
			CAST(l1.attribute_value AS DECIMAL(8,3)) ASC""" % (bm, conditions_it), as_list=1)


	for i in range(0, len(data)):

		if data[i][9] is None:
			ROL=0
		else:
			ROL = data[i][9]

		if data[i][10] is None:
			SO=0
		else:
			SO = data[i][10]

		if data[i][11] is None:
			PO=0
		else:
			PO = data[i][11]

		if data[i][12] is None:
			PLAN=0
		else:
			PLAN = data[i][12]
			
		if data[i][13] is None:
			IND=0
		else:
			IND = data[i][13]

		if data[i][15] is None:
			BRM=0
		else:
			BRM = data[i][15]

		if data[i][16] is None:
			DRM=0
		else:
			DRM = data[i][16]

		if data[i][17] is None:
			BGH=0
		else:
			BGH = data[i][17]

		if data[i][18] is None:
			DEL=0
		else:
			DRM = data[i][18]

		if data[i][19] is None:
			Dead=0
		else:
			Dead = data[i][19]

		total = (DRM + BRM + PLAN + PO + IND + BGH + DEL + Dead)

		stock = DRM + BRM + BGH + DEL + Dead
		prod = total - stock
		fut_stock = "X"

		if ROL <10:
			ROL = 3*ROL
		elif 10<=ROL < 20:
			ROL = 2*ROL
		elif 20<=ROL<50:
			ROL = 1.5*ROL

		if total < SO:
			fut_stock = "Raise More PO and Indent"
		elif total < SO + ROL:
			fut_stock = "1<30 Days"
		elif total < SO + 2*ROL:
			fut_stock = "2<60 Days"
		elif total < SO + 3*ROL:
			fut_stock = "3<90 Days"
		elif total < SO + 4*ROL:
			fut_stock = "4<120 Days"
		elif total < SO + 5*ROL:
			fut_stock = "5<150 Days"
		elif total < SO + 6*ROL:
			fut_stock = "6<180 Days"
		elif total > SO + 6*ROL:
			if ROL >0:
				fut_stock = "7 Over Stocked >180 Days"
			else:
				fut_stock = "-"
		else:
			fut_stock = "-"
			
		if stock < SO:
			cur_stock = "NO STOCK"
		elif stock < SO + ROL:
			cur_stock = "1<30 Days"
		elif stock < SO + 2*ROL:
			cur_stock = "2<60 Days"
		elif stock < SO + 3*ROL:
			cur_stock = "3<90 Days"
		elif stock < SO + 4*ROL:
			cur_stock = "4<120 Days"
		elif stock < SO + 5*ROL:
			cur_stock = "5<150 Days"
		elif stock < SO + 6*ROL:
			cur_stock = "6<180 Days"
		elif stock > SO + 6*ROL:
			if ROL >0:
				cur_stock = "7 Over Stocked >180 Days"
			else:
				cur_stock = "-"
		else:
			cur_stock = "-"

		data[i].insert (9, fut_stock)
		data[i].insert(10, cur_stock)
		data[i].insert (11, total)

	for j in range(0,len(data)):
		for k in range(0, len(data[j])):
			if data[j][k] ==0:
				data[j][k] = None
				
	attributes = ['Is RM', 'Brand', '%Quality', 'Special Treatment',
	'Tool Type', 'Material to Machine', 'Purpose', 'Type Selector',
	'd1_mm', 'w1_mm', 'l1_mm']
	
	float_fields = ['d1_mm', 'w1_mm', 'l1_mm']
	
	return data
	
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

