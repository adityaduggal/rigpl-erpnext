# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

TYPES = ("Drawing", "Standard")
DOCSTATUS = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
# filter: Important Documents field
FIELD_FILTERS = {"std_auth": "standard_authority", "category": "category_name", "based_on": "drawing_based_on",
	"item": "item", "customer": "customer", "sales_order": "sales_order"}


def execute(filters=None):
	filters = filters or {}
	if filters.get("type") not in TYPES:
		frappe.throw("Select Drawing or Standard", title="Type Needed")
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
	idoc = frappe.qb.DocType("Important Documents")
	if filters["type"] == "Drawing":
		query = (
			frappe.qb.from_(idoc)
			.select(idoc.name, idoc.drawing_based_on, idoc.customer, idoc.sales_order, idoc.item, idoc.description,
				idoc.remarks, idoc.docstatus)
			.orderby(idoc.drawing_based_on)
			.orderby(idoc.customer)
			.orderby(idoc.item)
		)
	else:
		query = (
			frappe.qb.from_(idoc)
			.select(idoc.name, idoc.standard_authority, idoc.standard_number, idoc.category_name, idoc.standard_year,
				idoc.committee, idoc.description, idoc.remarks, idoc.docstatus)
			.orderby(idoc.category_name)
			.orderby(idoc.standard_authority)
			.orderby(idoc.standard_number)
		)
	query = query.where(idoc.type == filters["type"])
	if filters.get("docstatus") in DOCSTATUS:
		query = query.where(idoc.docstatus == DOCSTATUS[filters["docstatus"]])
	else:
		query = query.where(idoc.docstatus != 2)
	# The Standard No is a LIKE pattern: the user can type % as a wildcard
	if filters.get("std_no"):
		query = query.where(idoc.standard_number.like(filters["std_no"]))
	for key, field in FIELD_FILTERS.items():
		if filters.get(key):
			query = query.where(idoc[field] == filters[key])
	return query.run(as_list=1)
