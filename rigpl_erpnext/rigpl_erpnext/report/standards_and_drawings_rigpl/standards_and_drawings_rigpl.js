// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Standards and Drawings RIGPL"] = {
	"formatter": rigpl_erpnext.report.blank_zero_formatter,
	"onload": function(report) {
		frappe.model.with_doctype("Important Documents", () => {
			const filter = report.get_filter("std_auth");
			filter.df.options = frappe.meta.get_docfield("Important Documents", "standard_authority").options;
			filter.refresh();
		});
	},
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
			"depends_on": "eval:doc.type === 'Standard'",
			"label": "Standard Authority",
			"fieldtype": "Select",
			"reqd": 0
		},
		{
			"fieldname":"std_no",
			"depends_on": "eval:doc.type === 'Standard'",
			"label": "Standard Number",
			"fieldtype": "Data",
			"reqd": 0
		},
		{
			"fieldname":"category",
			"depends_on": "eval:doc.type === 'Standard'",
			"label": "Category",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_tt_query"}}
		},
		{
			"fieldname":"based_on",
			"depends_on": "eval:doc.type === 'Drawing'",
			"label": "Drawing Based On",
			"fieldtype": "Select",
			"reqd": 0,
			"options": "\nSales Order\nItem\nCustomer"
		},
		{
			"fieldname":"item",
			"depends_on": "eval:doc.type === 'Drawing'",
			"label": "Item",
			"fieldtype": "Link",
			"reqd": 0,
			"options": "Item"
		},
		{
			"fieldname":"sales_order",
			"depends_on": "eval:doc.type === 'Drawing'",
			"label": "Sales Order",
			"fieldtype": "Link",
			"reqd": 0,
			"options": "Sales Order"
		},
		{
			"fieldname":"customer",
			"depends_on": "eval:doc.type === 'Drawing'",
			"label": "Customer",
			"fieldtype": "Link",
			"reqd": 0,
			"options": "Customer"
		},
	]
}
