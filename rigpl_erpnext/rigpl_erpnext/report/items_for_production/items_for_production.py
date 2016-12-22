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
		"Item:Link/Item:80", 
		
		###Below are attribute fields
		"RM::30", "Brand::40", "Qual::50", "SPL::50", "TT::60",
		"D1:Float:40", "W1:Float:40", "L1:Float:50",
		"D2:Float:40", "L2:Float:40", "Zn:Int:40",
		###Above are Attribute fields
		
		"CUT::120","URG::120",
		{"label": "Total", "fieldtype": "Float", "precision": 2, "width": 50},
		"RO:Int:40", "SO:Int:40", "PO:Int:40",
		"PL:Int:40","DE:Int:40", "BG:Int:40",
		"Description::300",
		{"label": "BRM", "fieldtype": "Float", "precision": 3, "width": 50},
		"BRG:Int:50", "BHT:Int:50", "BFG:Int:50", "BTS:Int:50",
		{"label": "DRM", "fieldtype": "Float", "precision": 3, "width": 50},
		"DSL:Int:50", "DRG:Int:50", "DFG:Int:50", "DTS:Int:50",
		"DRJ:Int:50", "DCN:Int:50", "BCN:Int:50", "PList::30", "TOD::30"
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
		CAST(d2.attribute_value AS DECIMAL(8,3)), 
		CAST(l2.attribute_value AS DECIMAL(8,3)),
		CAST(zn.attribute_value AS UNSIGNED),
		if(ro.warehouse_reorder_level=0, NULL ,ro.warehouse_reorder_level),
		if(sum(bn.reserved_qty)=0,NULL,sum(bn.reserved_qty)),
		if(sum(bn.ordered_qty)=0,NULL,sum(bn.ordered_qty)),
		if(sum(bn.planned_qty)=0,NULL,sum(bn.planned_qty)),

		if(min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)),

		it.description,	
		
		if(min(case WHEN bn.warehouse="RM-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="RM-BGH655 - RIGPL" THEN bn.actual_qty end)),
		
		if(min(case WHEN bn.warehouse="RG-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="RG-BGH655 - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="HT-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="HT-BGH655 - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="FG-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="FG-BGH655 - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="TEST-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="TEST-BGH655 - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="RM-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="RM-DEL20A - RIGPL" THEN bn.actual_qty end)) ,
			
		if(min(case WHEN bn.warehouse="SLIT-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="SLIT-DEL20A - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="RG-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="RG-DEL20A - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="FG-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="FG-DEL20A - RIGPL" THEN bn.actual_qty end)) ,

		if(min(case WHEN bn.warehouse="TEST-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="TEST-DEL20A - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="REJ-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="REJ-DEL20A - RIGPL" THEN bn.actual_qty end)),

		if(min(case WHEN bn.warehouse="CN-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="CN-DEL20A - RIGPL" THEN bn.actual_qty end)),
			
		if(min(case WHEN bn.warehouse="CN-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
			min(case WHEN bn.warehouse="CN-BGH655 - RIGPL" THEN bn.actual_qty end)),
			
		it.pl_item,
		it.stock_maintained

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
			CAST(l2.attribute_value AS DECIMAL(8,3)) ASC""" % (bm, conditions_it), as_list=1)

	subcon = frappe.db.sql("""SELECT bn.item_code, bn.actual_qty FROM `tabBin` bn, `tabWarehouse` wh
		WHERE wh.is_subcontracting_warehouse = 1 AND bn.actual_qty > 0 
		AND wh.name = bn.warehouse""", as_dict = 1)
	for i in range(0, len(data)):
		v_rate = frappe.db.sql("""SELECT valuation_rate FROM `tabValuation Rate`
			WHERE disabled = 'No' AND item_code = '%s'""" %data[i][0], as_list=1)
		
		if v_rate:	
			VR = flt(v_rate[0][0])
		else:
			VR = 0
		
		if data[i][12] is None:
			ROL=0
		else:
			ROL = data[i][12]

		if data[i][13] is None:
			SO=0
		else:
			SO = data[i][13]

		if data[i][14] is None:
			PO=0
		else:
			PO = data[i][14]
		
		for d in subcon:
			if d.item_code == data[i][0]:
				data[i][14] = PO + flt(d.actual_qty)
				PO = data[i][14]
		
		if data[i][15] is None:
			PLAN=0
		else:
			PLAN = data[i][15]

		if data[i][16] is None:
			DEL = 0
		else:
			DEL = data[i][16]

		if data[i][17] is None:
			BGH=0
		else:
			BGH = data[i][17]

		if data[i][19] is None:
			BRM=0
		else:
			BRM = data[i][19]
			
		if data[i][20] is None:
			BRG=0
		else:
			BRG = data[i][20]

		if data[i][21] is None:
			BHT=0
		else:
			BHT = data[i][21]

		if data[i][22] is None:
			BFG=0
		else:
			BFG = data[i][22]

		if data[i][23] is None:
			BTS=0
		else:
			BTS = data[i][23]

		if data[i][24] is None:
			DRM=0
		else:
			DRM = data[i][24]
			
		if data[i][25] is None:
			DSL=0
		else:
			DSL = data[i][25]

		if data[i][26] is None:
			DRG=0
		else:
			DRG = data[i][26]

		if data[i][27] is None:
			DFG=0
		else:
			DFG = data[i][27]

		if data[i][28] is None:
			DTEST=0
		else:
			DTEST = data[i][28]
			
		if data[i][30] is None:
			DCN=0
		else:
			DCN = data[i][30]

		if data[i][31] is None:
			BCN=0
		else:
			BCN = data[i][31]

		total = (DEL + BGH + BRG + BHT + BFG + BTS
		+ DSL + DRG + DFG + DTEST + DRM + BRM + DCN + BCN
		+ PLAN + PO)

		stock = DEL + BGH
		prd_qty = total - stock

		if 0 < ROL*VR <= 1000:
			ROL = 5*ROL
		elif 1000 < ROL*VR <= 2000:
			ROL = 2.5*ROL
		elif 2000 < ROL*VR <= 5000:
			ROL = 1.5*ROL

		if total < SO:
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
		if urg <> "":
			c_qty = ((2 * ROL) + SO - total)
			urg = urg + " Qty= " + str(c_qty)


		if stock < SO:
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
		if prd <> "":
			shortage = (2 * ROL) - stock
			if shortage < prd_qty:
				prd = prd + " Qty= " + str(shortage)
			else:
				prd = prd + " Qty = " + str(prd_qty)
		

		data[i].insert (12, urg)
		data[i].insert (13, prd)
		data[i].insert (14, total)

	for j in range(0,len(data)):
		for k in range(0, len(data[j])):
			if data[j][k] ==0:
				data[j][k] = None
				
	attributes = ['Is RM', 'Brand', '%Quality', 'Special Treatment',
	'Tool Type', 'Material to Machine', 'Purpose', 'Type Selector',
	'd1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm']
	
	float_fields = ['d1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm']
	
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

