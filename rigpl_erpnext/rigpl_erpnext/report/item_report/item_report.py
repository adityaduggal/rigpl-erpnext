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
		"Item:Link/Item:130", "Brand::80", "TT::80", "BM::60", "QLT::60",
		"Zn:Float:60", "SPL Treat::60", "D:Float:50", "D In::50", "D1:Float:50",
		"D1 In::50", "W:Float:50","W In::50", "L:Float:50", "L In::50",
		"L1:Float:50","L1 In::50", "D2:Float:5","D2 In::50","L2:Float:50",
		"L2 In:Float:50","A1:Int:30","A2:Int:30", "A3:Int:30", "R1:Float:30",
		"DType::40","DI::30","D1I::30","WI::30","LI::30","L1I::30", "D2I::30",
		"L2I::30", "Description::300", "Item Group:Link/Item Group:250", "RM::60",
		"PL::60", "TOD::30", "EOL:Date:30", "Item Name::300","Show in Web::60", "Web WH::80",
		"Weightage:Int:60", "Web Image::80", "Web Desc::100"
	]

def get_items(filters):
	conditions = get_conditions(filters)
	
	query = """SELECT t.name, IFNULL(t.brand,"-"), IFNULL(t.tool_type,"-"),
		IFNULL(t.base_material,"-"), IFNULL(t.quality,"-"), if(t.no_of_flutes=0,NULL,t.no_of_flutes),
		ifnull(t.special_treatment,"-"),
		if(t.height_dia=0,NULL,t.height_dia), ifnull(t.height_dia_inch,"-"),
		if(t.d1=0,NULL,t.d1), ifnull(t.d1_inch,"-"),
		if(t.width=0,NULL,t.width), ifnull(t.width_inch,"-"),
		if(t.length=0,NULL,t.length), ifnull(t.length_inch,"-"),
		if(t.l1=0,NULL,t.l1), ifnull(t.l1_inch,"-"),
		if(t.d2=0,NULL,t.d2), ifnull(t.d2_inch,"-"),
		if(t.l2=0,NULL,t.l2), ifnull(t.l2_inch,"-"),
		if(t.a1=0,NULL,t.a1), if(t.a2=0,NULL,t.a2), if(t.a3=0,NULL,t.a3), if(t.r1=0,NULL,t.r1),
		ifnull(t.drill_type,"-"), if(t.inch_h=1,1,"-"), if(t.inch_d1,1,"-"), if(t.inch_w,1,"-"),
		if(t.inch_l,1,"-"), if(t.inch_l1,1,"-"), if(t.inch_d2,1,"-"), if(t.inch_l2,1,"-"),
		ifnull(t.description,"-"), ifnull(t.item_group,"-"), ifnull(t.is_rm,"-"),
		ifnull(t.pl_item,"-"), ifnull(t.stock_maintained,"-"), ifnull(t.end_of_life,'2099-12-31'),
		ifnull(t.item_name,"--"), ifnull(t.show_in_website,2),ifnull(t.website_warehouse,"--"),
		ifnull(t.weightage,0), ifnull(t.website_image,"--"), ifnull(web_long_description,"--")
		FROM `tabItem` t where ifnull(t.end_of_life, '2099-12-31') > CURDATE() %s
		ORDER BY
		t.is_rm, t.base_material, t.quality, t.tool_type, t.no_of_flutes, t.special_treatment,
		t.d1, t.l1, t.height_dia, t.width, t.length, t.d2, t.l2""" % conditions

	
	data= frappe.db.sql(query, as_list=1)


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
