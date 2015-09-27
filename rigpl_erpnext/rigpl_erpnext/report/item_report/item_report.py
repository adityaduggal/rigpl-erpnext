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
		"Item:Link/Item:100", "RM::30", "BM::60","Brand::50","Quality::50", "SPL::50", 
		"TT::100", "MTM::100", "Purpose::100", "Type::100",
		"D1:Float:50","W1:Float:50", "L1:Float:60", 
		"D2:Float:50", "L2::50", "D3::50", "L3::50",
		"D1_Inch::50", "W1_Inch::50", "L1_Inch::50"
	]

def get_items(filters):
	conditions = get_conditions(filters)

	data = frappe.db.sql("""SELECT it.name FROM `tabItem` it""", as_list=1)

	attributes = ['Is RM', 'Base Material', 'Brand', '%Quality', 'Special Treatment',
		'Tool Type', 'Material to Machine', 'Purpose', 'Type Selector',
		'd1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm', 'd3_mm', 'l3_mm',
		'd1_inch', 'w1_inch', 'l1_inch']
	
	float_fields = ['d1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm', 
		'd3_mm', 'l3_mm',]
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
				data[i].extend([float(att[0][0])])
			else:
				data[i].extend(att[0])
	data = sorted (data, key = lambda x:(x[1], x[3], x[5], x[6], x[7]))
	return data

def get_conditions(filters):
	conditions = ""

	a= filters.get("brand")
	b= filters.get("material")
	c= filters.get("quality")
	d= filters.get("tool_type")
	e= filters.get("is_rm")
	f= filters.get("special")

	if f is None:
		if b is None or c is None or d is None or e is None:
			frappe.msgprint("Please select ALL of Material, Quality, Tool Type, Is RM", raise_exception=1)

	if filters.get("brand"):
		conditions += " and t.brand = '%s'" % filters["brand"]

	if filters.get("material"):
		conditions += " and t.base_material = '%s'" % filters["material"]

	if filters.get("quality"):
		conditions += " and t.quality = '%s'" % filters["quality"]

	if filters.get("tool_type"):
		conditions += " and t.tool_type = '%s'" % filters["tool_type"]

	if filters.get("is_rm"):
		if filters.get("is_rm")=="Yes":
			conditions += " and t.is_rm = '%s'" % filters["is_rm"]
		else:
			conditions += " and t.is_rm in ('%s' , NULL)" % filters["is_rm"]


	if filters.get("show_in_website") ==1:
		conditions += " and t.show_in_website =%s" % filters["show_in_website"]

	if filters.get("item"):
		conditions += " and t.name = '%s'" % filters["item"]


	return conditions
