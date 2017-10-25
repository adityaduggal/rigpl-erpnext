# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data
	
def get_columns(filters):
	return ["Invoice#:Link/Sales Invoice:120", "Item Code::60","Description::500",
			"Qty:Float:50", "Rate:Currency:80"]

def get_data(filters):
	name = filters.get("id")
	data = frappe.db.sql("""SELECT si.name, sid.item_code, sid.description, sid.qty, sid.rate,
		sid.cetsh_number
		FROM `tabSales Invoice` si, `tabSales Invoice Item` sid
		WHERE sid.parent = si.name AND si.docstatus = 1
			AND si.name = '%s' 
		ORDER BY sid.idx ASC""" % name , as_list=1)

	ctn = frappe.db.sql ("""SELECT name, item_code FROM `tabCustoms Tariff Number`""", as_list=1)
	if ctn:
		for c in ctn:
			for i in range(len(data)):
				if c[0] == data[i][5]:
					data[i][1] = c[1]
	if len(data) > 1:
		for i in range(len(data)):
			if i > 0:
				data[i][0] = ""
	return data
