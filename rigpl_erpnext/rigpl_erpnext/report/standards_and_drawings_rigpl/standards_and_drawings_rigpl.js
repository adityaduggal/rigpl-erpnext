// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Standards and Drawings RIGPL"] = {
	"filters": [
		{
			"fieldname":"type",
			"label": "Type of Document",
			"fieldtype": "Select",
			"reqd": 1,
			"options": "\nDrawing\nStandard"
		},
		{
			"fieldname":"docstatus",
			"label": "Document Status",
			"fieldtype": "Select",
			"reqd": 0,
			"options": "\nDraft\nSubmitted\nCancelled"
		},
		{
			"fieldname":"std_auth",
			"label": "Standard Authority",
			"fieldtype": "Select",
			"reqd": 0,
			"options": "\nBIS\nISO\nDIN"
		},
		{
			"fieldname":"std_no",
			"label": "Standard Number",
			"fieldtype": "Data",
			"reqd": 0
		},
		{
			"fieldname":"category",
			"label": "Category",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_tt_query"}}
		},
		{
			"fieldname":"based_on",
			"label": "Drawing Based On",
			"fieldtype": "Select",
			"reqd": 0,
			"options": "\nSales Order\nItem\nCustomer"
		},
		{
			"fieldname":"item",
			"label": "Item",
			"fieldtype": "Link",
			"reqd": 0,
			"options": "Item"
		},
		{
			"fieldname":"sales_order",
			"label": "Sales Order",
			"fieldtype": "Link",
			"reqd": 0,
			"options": "Sales Order"
		},
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"reqd": 0,
			"options": "Customer"
		},
	]
}
