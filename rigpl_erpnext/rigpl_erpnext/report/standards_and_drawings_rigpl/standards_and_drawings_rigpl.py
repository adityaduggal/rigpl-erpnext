# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

from rigpl_erpnext.utils.report_utils import blank_zeros

TYPES = ("Drawing", "Standard")
DOCSTATUS = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
COLUMN_FIELDS = {
	"Drawing": ["name", "drawing_based_on", "customer", "sales_order", "item", "description", "remarks",
		"docstatus"],
	"Standard": ["name", "standard_authority", "standard_number", "category_name", "standard_year", "committee",
		"description", "remarks", "docstatus"],
}
ORDER_BY = {
	"Drawing": "drawing_based_on, customer, item",
	"Standard": "category_name, standard_authority, standard_number",
}
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
	# get_list applies the User Permissions of the user
	rows = frappe.get_list("Important Documents", filters=get_conditions(filters),
		fields=COLUMN_FIELDS[filters["type"]], order_by=ORDER_BY[filters["type"]], limit_page_length=0,
		as_list=True)
	status_names = {docstatus: name for name, docstatus in DOCSTATUS.items()}
	# The status is the last column
	return [blank_zeros([*row[:-1], status_names[row[-1]]]) for row in rows]


def get_conditions(filters):
	conditions = [["type", "=", filters["type"]]]
	if filters.get("docstatus") in DOCSTATUS:
		conditions.append(["docstatus", "=", DOCSTATUS[filters["docstatus"]]])
	else:
		conditions.append(["docstatus", "!=", DOCSTATUS["Cancelled"]])
	# The Standard No is a LIKE pattern: the user can type % as a wildcard
	if filters.get("std_no"):
		conditions.append(["standard_number", "like", filters["std_no"]])
	conditions += [[field, "=", filters[key]] for key, field in FIELD_FILTERS.items() if filters.get(key)]
	return conditions
