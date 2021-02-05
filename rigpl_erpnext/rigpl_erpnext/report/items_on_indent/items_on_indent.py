#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	return[
		"Indent#:Link/Material Request:100", "Date:Date:80", "Schedule Date:Date:80", "Item Code:Link/Item:140",
		"Description::250", "Qty:Float:80", "UoM::20", "Ordered:Float:80", "BM::50",
		"Material Grade::80", "Type of Tool::150", "D1:Float:50", "W1:Float:50"
	]


def get_data(filters):
	bm = filters.get("bm")
	cond = get_cond(filters)
	query = """SELECT mr.name, mr.transaction_date, mri.schedule_date, mri.item_code, mri.description, mri.qty,
	mri.uom, mri.ordered_qty, IFNULL(bm.attribute_value, "-"), IFNULL(qa.attribute_value, "-"),
	IFNULL(tt.attribute_value, "-"), CAST(d1.attribute_value AS DECIMAL(8,3)), CAST(w1.attribute_value AS DECIMAL(8,3))
	FROM `tabMaterial Request` mr ,`tabMaterial Request Item` mri
		LEFT JOIN `tabItem Variant Attribute` bm ON mri.item_code = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` qa ON mri.item_code = qa.parent
			AND qa.attribute = '%s Quality'
		LEFT JOIN `tabItem Variant Attribute` tt ON mri.item_code = tt.parent
			AND tt.attribute = 'Tool Type'
		LEFT JOIN `tabItem Variant Attribute` d1 ON mri.item_code = d1.parent
			AND d1.attribute = 'd1_mm'
		LEFT JOIN `tabItem Variant Attribute` w1 ON mri.item_code = w1.parent
			AND w1.attribute = 'w1_mm'
	WHERE mri.parent = mr.name AND mr.docstatus = 1 AND mr.status != "Stopped" 
	AND IFNULL(mri.ordered_qty,0) < IFNULL(mri.qty,0) %s
	ORDER BY bm.attribute_value, tt.attribute_value, qa.attribute_value, 
	CAST(d1.attribute_value AS DECIMAL(8,3)), CAST(w1.attribute_value AS DECIMAL(8,3))""" % (bm, cond)
	data = frappe.db.sql(query, as_list=1)
	return data


def get_cond(filters):
	cond = ""
	if filters.get("date"):
		cond += " AND mr.transaction_date <= '%s'" % filters.get("date")
	if filters.get("bm"):
		cond += " AND bm.attribute_value = '%s'" % filters.get("bm")
	if filters.get("tt"):
		cond += " AND tt.attribute_value = '%s'" % filters.get("tt")
	if filters.get("qa"):
		cond += " AND qa.attribute_value = '%s'" % filters.get("qa")
	return cond
