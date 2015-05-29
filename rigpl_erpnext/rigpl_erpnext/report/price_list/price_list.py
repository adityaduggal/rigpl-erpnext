from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_item_data(filters)

	return columns, data

def get_columns():
	return [
		"PL ID:Link/Item Price:100", "PL::60", "Item:Link/Item:120", "Description::350", 
		"List Price:Currency:100",
		"Cur::40", "Brand::100", "BM::70", "QLT::60", "TT::100", "SPL::50",
		"HD:Float:50", "W:Float:50", "L:Float:50", "Zn:Float:50", "D1:Float:50",
		"L1:Float:50", "a1:Float:50", "D2:Float:50", "L2:Float:50", "a2:Float:50",
		"r1:Float:50", "a3:Float:50", "DT::50","H In::50", "W In::50", "L In::50",
		"D1 In::50", "L1 In::50", "D2 In::50", "L2 In::50", "Is PL::50"
	]

def get_item_data(filters):
	conditions = get_conditions(filters)
	conditions_itp = get_conditions_item_price(filters)


	data = frappe.db.sql("""select it.name, it.description, it.brand, it.base_material, it.quality, it.tool_type,
	it.special_treatment, it.height_dia, it.width, it.length, it.no_of_flutes, it.d1, it.l1, it.a1,
	it.d2, it.l2, it.a2, it.r1, it.a3, it.drill_type, it.height_dia_inch, it.width_inch,
	it.length_inch, it.d1_inch, it.l1_inch, it.d2_inch, it.l2_inch, it.pl_item
	from `tabItem` it where ifnull(it.end_of_life, '2099-12-31') > CURDATE() %s
	order by it.base_material, it.quality, it.tool_type, it.special_treatment, it.height_dia, it.width,
	it.d1, it.l1""" %conditions , as_list=1)

	item_price = frappe.db.sql("""select itp.price_list, itp.item_code, itp.price_list_rate, itp.currency, itp.name
	from `tabItem Price` itp %s order by itp.item_code""" %conditions_itp, as_list=1)

	#last_so = frappe.db.sql("""select so.customer, max(so.transaction_date), so.name
	#from `tabSales Order` so where so.docstatus = 1 group by so.customer""", as_list=1)


	#loop to add prices to the Item Table
	for i in data:
		if any (i[0] in s for s in item_price):
			for j in item_price:
				if i[0] == j[1]:
					i.insert(0, j[4]) #insert price list id
					i.insert(1, j[0]) #insert Price list name
					i.insert(4, j[2]) #insert price value
					i.insert(5, j[3]) #insert currency of value

		else:
			i.insert(0, "NA")
			i.insert(1,"PL?")
			i.insert(4, "0")
			i.insert(5, "NP")
	return data


def get_conditions(filters):
	conditions = ""

	if filters.get("tt"):
		conditions += " and it.tool_type = '%s'" % filters["tt"]

	if filters.get("bm"):
		conditions += " and it.base_material = '%s'" % filters["bm"]

	if filters.get("quality"):
		conditions += " and it.quality = '%s'" % filters["quality"]

	if filters.get("item"):
		conditions += " and it.name = '%s'" % filters["item"]

	return conditions

def get_conditions_item_price(filters):
	conditions_itp = ""

	if filters.get("price_list"):
		conditions_itp += " WHERE itp.price_list = '%s'" % filters["price_list"]

	return conditions_itp
