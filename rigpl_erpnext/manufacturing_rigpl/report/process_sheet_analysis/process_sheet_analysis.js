// Copyright (c) 2016, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
/* eslint-disable */

const DEFAULT_VIEW = "Process Sheets";
const PENDING = "Pending Process Sheets";
const PROCESS_WISE = "Process Wise Details";
const RM_USED = "RM Used Details";

function in_views(...views) {
	return "eval:" + JSON.stringify(views) + ".includes(doc.view)";
}

frappe.query_reports["Process Sheet Analysis"] = {
	"filters": [
		{
			"fieldname":"view",
			"label": "View",
			"fieldtype": "Select",
			"options": [DEFAULT_VIEW, PENDING, PROCESS_WISE, RM_USED].join("\n"),
			"default": DEFAULT_VIEW,
			"reqd": 1
		},
		{
			"fieldname":"status",
			"label": "Status",
			"fieldtype": "Select",
			"options": "\nCancelled\nCompleted\nDraft\nIn Progress\nShort Closed\nStopped\nSubmitted",
			"default": "Draft",
			"depends_on": in_views(DEFAULT_VIEW)
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_bm_query"}}
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_tt_query"}}
		},
		{
			"fieldname":"series",
			"label": "Series",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_series_query"}}
		},
		{
			"fieldname":"spl",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_spl_query"}}
		},
		{
			"fieldname":"item",
			"label": "Item",
			"fieldtype": "Link",
			"options": "Item",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item', 'has_variants','=', 0]]}}
		},
		{
			"fieldname":"so",
			"label": "Sales Order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Sales Order', 'docstatus','=', 1]]}}
		},
		{
			"fieldname":"show_zero_qty",
			"label": "Show Zero Qty Process Sheet",
			"fieldtype": "Check",
			"depends_on": in_views(DEFAULT_VIEW)
		}
	],
	"formatter": rigpl_erpnext.report.blank_zero_formatter,
};
