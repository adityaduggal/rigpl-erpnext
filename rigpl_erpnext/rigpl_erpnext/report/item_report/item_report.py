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
		"A1_DEG:Float:50",
		"D1_Inch::50", "W1_Inch::50", "L1_Inch::50",
		"CETSH::150",
		"Template or Variant Of:Link/Item:200", "Description::300",
		"Creation:Date:100"
	]

def get_items(filters):
	conditions_it = get_conditions(filters) [0]

	query = """SELECT it.name, it.variant_of, it.description, it.creation FROM `tabItem` it 
		WHERE ifnull(it.end_of_life, '2099-12-31') > CURDATE() %s""" % conditions_it

	data = frappe.db.sql(query, as_list=1)
	
	attributes = ['Is RM', 'Base Material', 'Brand', '%Quality', 'Special Treatment',
		'Tool Type', 'Material to Machine', 'Purpose', 'Type Selector',
		'd1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm', 'd3_mm', 'l3_mm',
		'a1_deg',
		'd1_inch', 'w1_inch', 'l1_inch',
		'CETSH Number',]
	
	float_fields = ['d1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm', 
		'd3_mm', 'l3_mm', 'a1_deg']
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
				data[i].insert(len(data[i])-3,[float(att[0][0])])
			else:
				data[i].insert(len(data[i])-3, att[0])
	data = sorted (data, key = lambda x:(x[1], x[3], x[5], x[6], x[7]))
	return data

def get_conditions(filters):
	conditions_it = ""
	conditions_iva = ""

	if filters.get("brand"):
		conditions_iva += " and iva.brand = '%s'" % filters["brand"]

	if filters.get("material"):
		conditions_iva += " and iva.base_material = '%s'" % filters["material"]

	if filters.get("quality"):
		conditions_iva += " and iva.quality = '%s'" % filters["quality"]

	if filters.get("tool_type"):
		conditions_iva += " and iva.tool_type = '%s'" % filters["tool_type"]

	if filters.get("is_rm"):
		if filters.get("is_rm")=="Yes":
			conditions_iva += " and iva.is_rm = '%s'" % filters["is_rm"]
		else:
			conditions_iva += " and iva.is_rm in ('%s' , NULL)" % filters["is_rm"]


	if filters.get("show_in_website") ==1:
		conditions_it += " and it.show_in_website =%s" % filters["show_in_website"]

	if filters.get("item"):
		conditions_it += " and it.name = '%s'" % filters["item"]
	
	if filters.get("variant_of"):
		conditions_it += " and it.variant_of = '%s'" % filters["variant_of"]


	return conditions_it, conditions_iva
