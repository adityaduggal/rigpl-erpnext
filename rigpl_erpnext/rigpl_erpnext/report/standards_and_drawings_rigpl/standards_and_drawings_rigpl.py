# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	if filters.get("type") == 'Drawing':
		return[
			"DWG#:Link/Important Documents:100", "Based On::100", "Customer:Link/Customer:150",
			"SO#:Link/Sales Order:100", "Item Code:Link/Item:200", "Description::300",
			"Remarks::300", "Document Status::50"
		]
	else:
		return[
			"STD#:Link/Important Documents:100", "Issuing Authority::50", "Standard No::100",
			"Category::200", "Year:Int:80", "Committee::100", "Description::300","Remarks:300",
			"Document Status::50"
		]

def get_data(filters):
	conditions = get_conditions(filters)
	if filters.get("type") == "Drawing":
		query = """SELECT idoc.name, idoc.drawing_based_on, idoc.customer, idoc.sales_order, idoc.item,
			idoc.description, idoc.remarks, idoc.docstatus 
			FROM `tabImportant Documents` idoc
			WHERE %s"""%(conditions)
		data = frappe.db.sql(query, as_list=1)
	else:
		query = """SELECT idoc.name, idoc.standard_authority, idoc.standard_number, idoc.category_name, 
			idoc.standard_year, idoc.committee, idoc.description, idoc.remarks, idoc.docstatus 
			FROM `tabImportant Documents` idoc
			WHERE %s"""%(conditions)
		data = frappe.db.sql(query, as_list=1)
	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("type"):
		conditions += " idoc.type = '%s'" %(filters.get("type"))

	if filters.get("docstatus") == "Draft":
		conditions += " AND idoc.docstatus = 0"
	elif filters.get("docstatus") == "Submitted":
		conditions += " AND idoc.docstatus = 1"
	elif filters.get("docstatus") == "Cancelled":
		conditions += " AND idoc.docstatus = 2"
	else:
		conditions += " AND idoc.docstatus != 2"

	if filters.get("std_auth"):
		conditions += " AND idoc.standard_authority = '%s'" %(filters.get("std_auth"))

	if filters.get("std_no"):
		conditions += " AND idoc.standard_number LIKE '%s'" %(filters.get("std_no"))

	if filters.get("category"):
		conditions += " AND idoc.category_name = '%s'" %(filters.get("category"))

	if filters.get("based_on"):
		conditions += " AND idoc.drawing_based_on = '%s'" %(filtes.get("based_on"))

	if filters.get("item"):
		conditions += " AND idoc.item = '%s'" %(filters.get("item"))

	if filters.get("customer"):
		conditions += " AND idoc.customer = '%s'" %(filters.get("customer"))

	if filters.get("sales_order"):
		conditions += " AND idoc.customer = '%s'" %(filters.get("sales_order"))

	return conditions