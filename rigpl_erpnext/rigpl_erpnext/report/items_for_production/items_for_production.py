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
		"RM::30", "Brand::60", "Qual::50", "SPL::50", "TT::60", "MTM::60",
		"Purp::60", "Type::60", "D1:Float:30", "W1:Float:30", "L1:Float:30",
		"D2:Float:30", "L2:Float:30",
		###Above are Attribute fields
		
		"CUT::60","URG::60",
		{"label": "Total", "fieldtype": "Float", "precision": 2, "width": 50},
		"RO:Int:40", "SO:Int:40", "PO:Int:40",
		"PL:Int:40","DE:Int:40", "BG:Int:40",
		"Description::300",
		{"label": "BRM", "fieldtype": "Float", "precision": 3, "width": 50},
		"BRG:Int:50", "BHT:Int:50", "BFG:Int:50", "BTS:Int:50",
		{"label": "DRM", "fieldtype": "Float", "precision": 3, "width": 50},
		"DSL:Int:50", "DRG:Int:50", "DFG:Int:50", "DTS:Int:50",
		"DRJ:Int:50", "PList::30", "TOD::30"
	]

def get_items(filters):
	conditions = get_conditions(filters)

	data = frappe.db.sql("""SELECT it.name,
	if(it.re_order_level=0, NULL ,it.re_order_level),
	if(sum(bn.reserved_qty)=0,NULL,sum(bn.reserved_qty)),
	if(sum(bn.ordered_qty)=0,NULL,sum(bn.ordered_qty)),
	if(sum(bn.planned_qty)=0,NULL,sum(bn.planned_qty)),

	if(min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)),

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

	it.pl_item,
	it.stock_maintained

	FROM `tabItem` it left join `tabBin` bn on (it.name = bn.item_code)

	WHERE bn.item_code != ""
	AND bn.item_code = it.name
	AND it.tool_type != 'Others'
	AND ifnull(it.end_of_life, '2099-12-31') > CURDATE() %s

	group by bn.item_code""" % conditions, as_list=1)


	for i in range(0, len(data)):

		if data[i][1] is None:
			ROL=0
		else:
			ROL = data[i][1]

		if data[i][2] is None:
			SO=0
		else:
			SO = data[i][2]

		if data[i][3] is None:
			PO=0
		else:
			PO = data[i][3]

		if data[i][4] is None:
			PLAN=0
		else:
			PLAN = data[i][4]

		if data[i][5] is None:
			DEL = 0
		else:
			DEL = data[i][5]

		if data[i][6] is None:
			BGH=0
		else:
			BGH = data[i][6]

		if data[i][8] is None:
			BRM=0
		else:
			BRM = data[i][8]
			
		if data[i][9] is None:
			BRG=0
		else:
			BRG = data[i][9]

		if data[i][10] is None:
			BHT=0
		else:
			BHT = data[i][10]

		if data[i][11] is None:
			BFG=0
		else:
			BFG = data[i][11]

		if data[i][12] is None:
			BTS=0
		else:
			BTS = data[i][12]

		if data[i][13] is None:
			DRM=0
		else:
			DRM = data[i][13]
			
		if data[i][14] is None:
			DSL=0
		else:
			DSL = data[i][14]

		if data[i][15] is None:
			DRG=0
		else:
			DRG = data[i][15]

		if data[i][16] is None:
			DFG=0
		else:
			DFG = data[i][16]

		if data[i][17] is None:
			DTEST=0
		else:
			DTEST = data[i][17]

		total = (DEL + BGH + BRG + BHT + BFG + BTS
		+ DSL + DRG + DFG + DTEST + DRM + BRM
		+ PLAN + PO)

		stock = DEL + BGH
		prd = total - stock

		if ROL >=100:
			ROL = 1.5*ROL

		if total < SO:
			urg = "1C ORD"
		elif total < SO + (0.7*1.8*ROL):
			urg = "2C STK"
		elif total < SO + (0.8*1.8*ROL):
			urg = "3C STK"
		elif total < SO + (0.9*1.8*ROL):
			urg = "4C STK"
		elif total < SO + (1.8*ROL):
			urg = "5C STK"
		elif total < SO + (1.1*1.8*ROL):
			urg = "6C STK"
		else:
			urg = ""

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
		elif stock > SO + 5*ROL:
			if ROL >0:
				prd = "9 OVER"
			else:
				prd = ""
		else:
			prd = ""

		data[i].insert (1, urg)
		data[i].insert (2, prd)
		data[i].insert (3, total)

	for j in range(0,len(data)):
		for k in range(0, len(data[j])):
			if data[j][k] ==0:
				data[j][k] = None
				
	attributes = ['Is RM', 'Brand', '%Quality', 'Special Treatment',
	'Tool Type', 'Material to Machine', 'Purpose', 'Type Selector',
	'd1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm']
	
	float_fields = ['d1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm']
	
	for i in range(len(data)):
		att = []
		for j in attributes:
			att = frappe.db.sql("""SELECT ifnull(iva.attribute_value,"-")
				FROM `tabItem Variant Attribute` iva
				WHERE iva.attribute LIKE '%s'
				AND iva.parent = '%s'""" %(j,data[i][0]), as_list=1)
			if not att:
				att = ["-"]
			if j in float_fields and att[0][0] <> "-":
				data[i].insert((len(data[i])-22),[float(att[0][0])])
			else:
				data[i].insert((len(data[i])-22), att[0])
	
	return data
	
def get_conditions(filters):
	conditions = ""

	if filters.get("item"):
		conditions += " and it.name LIKE '%%s'" % filters["item"]

	if filters.get("is_rm"):
		conditions += " and it.is_rm = '%s'" % filters["is_rm"]

	if filters.get("quality"):
		conditions += " and it.quality = '%s'" % filters["quality"]

	if filters.get("tool_type"):
		conditions += " and it.tool_type = '%s'" % filters["tool_type"]

	if filters.get("brand"):
		conditions += " and it.brand = '%s'" % filters["brand"]

	if filters.get("special_treatment"):
		conditions += " and it.special_treatment = '%s'" % filters["special_treatment"]

	return conditions
