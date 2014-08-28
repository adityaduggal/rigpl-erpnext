from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_va_entries(filters)

	return columns, data

def get_columns():


	return [
		"Posting Date:Date:80", "Name:Link/Delivery Note:100" ,"Customer:Link/Customer:180",
		"Item Code:Link/Item:100","Description::250", "Quantity:Float/2:60",
		"Discount (%):Float/2:60", "Rate*:Float/2:60", "Amount*:Float/2:60",
		"Status::100", "Base Metal::100", "Tool Type::100", "Height or Dia (mm):Float/3:60",
		"Width (mm):Float/3:60", "Length (mm):Float/2:60", "Material::80",
		"D1:Float/3:60", "L1:Float/3:60", "Coating::80"
	]

def get_va_entries(filters):
	conditions = get_conditions(filters)

	dn = frappe.db.sql("""select dn.posting_date, dn.name, dn.customer,
		dni.item_code, dni.description, dni.qty, dni.discount_percentage, dni.base_rate,
		dni.base_amount, dn.status from `tabDelivery Note` dn , `tabDelivery Note Item` dni
		where dni.parent = dn.name and dn.status = "Submitted" %s
		order by posting_date asc, name asc, dni.item_code asc, dni.description asc"""
		% conditions, as_list=1)

	item = frappe.db.sql("""SELECT it.name, it.base_material, it.tool_type,
		it.height_dia, it.width, it.length, it.quality, it.d1, it.l1, it.special_treatment
		FROM `tabItem` it ORDER BY it.name""" , as_list=1)

	#frappe.msgprint(len(dn))
	for i in range(0, len(dn)):
		for j in range (0, len(item)):
			if dn[i][3]== item[j][0]:
				if (item[j][1]): #insert base material
					dn[i].insert(10,item[j][1])
				else:
					dn[i].insert(10,None)

				if (item[j][2]): #insert tool type
					dn[i].insert(11,item[j][2])
				else:
					dn[i].insert(11,None)

				if (item[j][3]): #insert h/d
					dn[i].insert(12,item[j][3])
				else:
					dn[i].insert(12,None)

				if (item[j][4]): #insert wd
					dn[i].insert(13,item[j][4])
				else:
					dn[i].insert(13,None)

				if (item[j][5]): #insert ln
					dn[i].insert(14,item[j][5])
				else:
					dn[i].insert(14,None)

				if (item[j][6]): #insert quality
					dn[i].insert(15,item[j][6])
				else:
					dn[i].insert(15,None)

				if (item[j][7]): #insert d1
					dn[i].insert(16,item[j][7])
				else:
					dn[i].insert(16,None)

				if (item[j][8]): #insert l1
					dn[i].insert(17,item[j][8])
				else:
					dn[i].insert(17,None)

				if (item[j][9]): #insert coating
					dn[i].insert(18,item[j][9])
				else:
					dn[i].insert(18,None)
	dn = sorted(dn, key = lambda k: (k[10], k[15], k[11], k[12],
		k[13], k[14], k[16], k[17], k[3], k[0], k[1]))
	return dn

def get_conditions(filters):
	conditions = ""
	if filters.get("from_date"):
		conditions += " and dn.posting_date >= '%s'" % filters["from_date"]
	else:
		frappe.msgprint("Please Select a From Date first", raise_exception=1)

	if filters.get("to_date"):
		conditions += " and dn.posting_date <= '%s'" % filters["to_date"]

	return conditions
