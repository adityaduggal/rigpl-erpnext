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
		"Item:Link/Item:130", "Description::350", "ROL:Int:60", "Sold:Int:60",
		"#Cust:Int:60", "# DN:Int:60", "Con:Int:60", "DNA:Int:60", "ConA:Int:60",
		"TotA:Int:80", "Diff:Int:60","BM::70", "TT::80",
		"Quality::80","H/D:Float:60", "W:Float:60",
		"L:Float:60", "D1:Float:60","L1:Float:60","Brand::100"
	]

def get_sl_entries(filters):
	conditions = get_conditions(filters)
	conditions_ste = get_conditions_ste(filters)
	conditions_it = get_conditions_it(filters)
	conditions_so = get_conditions_so(filters)

	if (filters.get("from_date")):
		diff = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days
		if diff < 0:
			frappe.msgprint ("From date has to be less than To Date", raise_exception=1)
	else:
		frappe.msgprint ("Please select from date first", raise_exception=1)

	DN_Qty= frappe.db.sql("""select sle.item_code, sum(sle.actual_qty)*-1
	from `tabStock Ledger Entry` sle where sle.voucher_type = "Delivery Note" and sle.is_cancelled = "No" %s
	group by sle.item_code order by sle.item_code"""
	% conditions, as_list=1)

	cust_nos = frappe.db.sql("""select sod.item_code, count(DISTINCT(so.customer))
	FROM `tabSales Order` so, `tabSales Order Item` sod
	WHERE sod.parent = so.name and so.docstatus = 1 %s
	group by sod.item_code order by sod.item_code"""
	% conditions_so, as_list=1)

	data = frappe.db.sql("""select it.name, it.description, if(it.re_order_level=0,NULL,it.re_order_level),
	it.base_material, it.tool_type, it.quality, it.height_dia, it.width, it.length, it.d1, it.l1
	FROM `tabItem` it WHERE ifnull(it.end_of_life, '2099-12-31') > CURDATE() %s
	ORDER BY it.base_material, it.quality, it.tool_type, it.height_dia,
	it.width, it.length, it.d1, it.l1, it.brand"""
	% conditions_it, as_list=1)


	SE_Qty = frappe.db.sql("""select sted.item_code, sum(sted.qty)
	from `tabStock Entry` ste, `tabStock Entry Detail` sted where sted.parent = ste.name
	and ste.docstatus = 1 and sted.s_warehouse IS NOT NULL and sted.t_warehouse IS NULL %s
	group by sted.item_code order by sted.item_code"""
	% conditions_ste, as_list=1)

	No_of_DN = frappe.db.sql("""select sle.item_code, (count(DISTINCT sle.voucher_no))*1
	from `tabStock Ledger Entry` sle where sle.voucher_type = "Delivery Note" and sle.is_cancelled = "No" %s
	group by sle.item_code order by sle.item_code"""
	% conditions, as_list=1)

	for i in data:
		#Below loop would add the Qty of DN to the data
		if any (i[0] in s for s in DN_Qty):
			for j in DN_Qty:
				if i[0] == j[0]:
					if j[1] is None:
						i.insert (3,None)
					else:
						i.insert (3,j[1])
		else:
			i.insert (3,None)

		#Below loop would add the number of customers buying the item
		if any (i[0] in t for t in cust_nos):
			for k in cust_nos:
				if i[0] == k[0]:
					if k[1] is None:
						i.insert(4,None)
					else:
						i.insert (4,k[1])
		else:
			i.insert (4,None)

			#Below loop would add the No of DNs to the data
		if any (i[0] in t for t in No_of_DN):
			for k in No_of_DN:
				if i[0] == k[0]:
					if k[1] is None:
						i.insert(5,None)
					else:
						i.insert (5,k[1])
		else:
			i.insert (5,None)

			#Below loop would add the Qty of Item Consumed to the data
		if any (i[0] in v for v in SE_Qty):
			for m in SE_Qty:
				if i[0] == m[0]:
					if m[1] is None:
						i.insert (6,None)
					else:
						i.insert(6, m[1])
		else:
			i.insert (6,None)

	#frappe.msgprint(type(data[1][3]))
	for i in range(0, len(data)):

		DN = data[i][3]
		STE = data[i][6]



		#Add Average DN Qty
		if type(DN) is float:
			data[i].insert (7,((DN/diff)*30))
		else:
			data[i].insert (7,None)

		#Add Averange Consumed Qty
		if type(STE) is float:
			data[i].insert (8,((STE/diff)*30))
		else:
			data[i].insert (8,None)

		DN_Avg = data[i][7]
		STE_Avg = data[i][8]
		ROL = data[i][2]

		if type(DN_Avg) is float and type(STE_Avg) is float:
			total = DN_Avg + STE_Avg
		elif type(DN_Avg) is float:
			total = DN_Avg
		elif type(STE_Avg) is float:
			total = STE_Avg
		else:
			total =None

		#Add Total Average of Consumption and Sale
		data[i].insert (9,total)

		#Add Difference between actual ROL and Calculated ROL
		if type(total) is float and type(ROL) is float:
			change = total - ROL
		elif type(total) is float:
			change = total
		elif type(ROL) is float:
			change = -ROL
		else:
			change = None
		data[i].insert (10,change)

	for i in range(0,len(data)):
		for j in range(0,len(data[i])):
			if type(data[i][j])is float:
				if data[i][j] ==0:
					data[i][j] = None

	return data

def get_conditions(filters):
	conditions = ""

	if filters.get("from_date"):
		conditions += " and sle.posting_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions += " and sle.posting_date <= '%s'" % filters["to_date"]

	return conditions

def get_conditions_ste(filters):
	conditions_ste = ""

	if filters.get("from_date"):
		conditions_ste += " and ste.posting_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions_ste += " and ste.posting_date <= '%s'" % filters["to_date"]

	return conditions_ste

def get_conditions_it(filters):
	conditions_it = ""

	if filters.get("item"):
		conditions_it += " and it.name = '%s'" % filters["item"]

	if filters.get("is_rm"):
		conditions_it += " and it.is_rm = '%s'" % filters["is_rm"]

	if filters.get("base_material"):
		conditions_it += " and it.base_material = '%s'" % filters["base_material"]

	if filters.get("tool_type"):
		conditions_it += " and it.tool_type = '%s'" % filters["tool_type"]

	if filters.get("quality"):
		conditions_it += " and it.quality = '%s'" % filters["quality"]

	return conditions_it

def get_conditions_so(filters):
	conditions_so = ""

	if filters.get("from_date"):
		conditions_so += " and so.transaction_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions_so += " and so.transaction_date <= '%s'" % filters["to_date"]

	return conditions_so
