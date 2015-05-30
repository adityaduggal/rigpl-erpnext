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
		"Item:Link/Item:130", "Qual::60", "TT::100",
		{"label": "D", "fieldtype": "Float", "precision": 3, "width": 50},
		{"label": "W", "fieldtype": "Float", "precision": 3, "width": 50},
		{"label": "L", "fieldtype": "Float", "precision": 1, "width": 50},
		"CUT::60",	"URG::60",
		{"label": "Total", "fieldtype": "Float", "precision": 2, "width": 50},
		"RO:Int:40", "SO:Int:40", "PO:Int:40",
		"PL:Int:40","DE:Int:40", "BG:Int:40",
		"Description::300",
		{"label": "D1", "fieldtype": "Float", "precision": 3, "width": 35},
		{"label": "L1", "fieldtype": "Float", "precision": 3, "width": 35},
		"RM::30",
		"BRG:Int:50", "BHT:Int:50", "BFG:Int:50", "BTS:Int:50",
		"DSL:Int:50", "DRG:Int:50", "DFG:Int:50", "DTS:Int:50",
		{"label": "DRM", "fieldtype": "Float", "precision": 3, "width": 50},
		{"label": "BRM", "fieldtype": "Float", "precision": 3, "width": 50},
		"DRJ:Int:50", "PList::30", "TOD::30"
	]

def get_items(filters):
	conditions = get_conditions(filters)

	data = frappe.db.sql("""SELECT it.name,ifnull(it.quality,"x"),
	it.tool_type,if(it.height_dia=0,NULL,it.height_dia),
	if(it.width=0,NULL,it.width),
	if(it.length=0,NULL,it.length),
	if(it.re_order_level=0, NULL ,it.re_order_level),
	if(sum(bn.reserved_qty)=0,NULL,sum(bn.reserved_qty)),
	if(sum(bn.ordered_qty)=0,NULL,sum(bn.ordered_qty)),
	if(sum(bn.planned_qty)=0,NULL,sum(bn.planned_qty)),

	if(min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="DEL20A - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="BGH655 - RIGPL" THEN bn.actual_qty end)),

	it.description, it.d1, it.l1,ifnull(it.is_rm,"No"),

	if(min(case WHEN bn.warehouse="RG-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="RG-BGH655 - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="HT-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="HT-BGH655 - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="FG-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="FG-BGH655 - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="TEST-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="TEST-BGH655 - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="SLIT-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="SLIT-DEL20A - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="RG-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="RG-DEL20A - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="FG-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="FG-DEL20A - RIGPL" THEN bn.actual_qty end)) ,

	if(min(case WHEN bn.warehouse="TEST-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="TEST-DEL20A - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="RM-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="RM-DEL20A - RIGPL" THEN bn.actual_qty end)) ,

	if(min(case WHEN bn.warehouse="RM-BGH655 - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="RM-BGH655 - RIGPL" THEN bn.actual_qty end)),

	if(min(case WHEN bn.warehouse="REJ-DEL20A - RIGPL" THEN bn.actual_qty end)=0,NULL,
		min(case WHEN bn.warehouse="REJ-DEL20A - RIGPL" THEN bn.actual_qty end)),

	it.pl_item,
	it.stock_maintained

	FROM `tabItem` it left join `tabBin` bn on (it.name = bn.item_code)

	WHERE bn.item_code != ""
	AND bn.item_code = it.name
	AND it.tool_type != 'Others'
	AND ifnull(it.end_of_life, '2099-12-31') > CURDATE() %s

	group by bn.item_code

	ORDER BY it.base_material asc,
	it.quality asc,
	it.tool_type asc,
	it.height_dia asc,
	it.width asc,
	it.length asc""" % conditions, as_list=1)


	for i in range(0, len(data)):
		#frappe.msgprint(data[i])
		if data[i][6] is None:
			ROL=0
		else:
			ROL = data[i][6]

		if data[i][7] is None:
			SO=0
		else:
			SO = data[i][7]

		if data[i][8] is None:
			PO=0
		else:
			PO = data[i][8]

		if data[i][9] is None:
			PLAN=0
		else:
			PLAN = data[i][9]

		if data[i][10] is None:
			DEL = 0
		else:
			DEL = data[i][10]

		if data[i][11] is None:
			BGH=0
		else:
			BGH = data[i][11]

		if data[i][16] is None:
			BRG=0
		else:
			BRG = data[i][16]

		if data[i][17] is None:
			BHT=0
		else:
			BHT = data[i][17]

		if data[i][18] is None:
			BFG=0
		else:
			BFG = data[i][18]

		if data[i][19] is None:
			BTS=0
		else:
			BTS = data[i][19]

		if data[i][20] is None:
			DSL=0
		else:
			DSL = data[i][20]

		if data[i][21] is None:
			DRG=0
		else:
			DRG = data[i][21]

		if data[i][22] is None:
			DFG=0
		else:
			DFG = data[i][22]

		if data[i][23] is None:
			DTEST=0
		else:
			DTEST = data[i][23]

		if data[i][24] is None:
			DRM=0
		else:
			DRM = data[i][24]

		if data[i][25] is None:
			BRM=0
		else:
			BRM = data[i][25]

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

		data[i].insert (6, urg)
		data[i].insert (7, prd)
		data[i].insert (8, total)

	for j in range(0,len(data)):
		for k in range(0, len(data[j])):
			if type(data[j][k]) is float:
				if data[j][k] ==0:
					data[j][k] = None

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
