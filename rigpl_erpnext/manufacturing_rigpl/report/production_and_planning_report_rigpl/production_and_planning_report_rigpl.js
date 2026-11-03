// Copyright (c) 2016, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
/* eslint-disable */

{
const PLANNING = "Production Planning";
const SUMMARY = "Post Production Summary";
const SO_WISE = "SO wise Summary";
const OP_TIME = "Operation Time Analysis";
const MACH_EFF = "Machine Efficiency";

function in_views(...views) {
	return "eval:" + JSON.stringify(views) + ".includes(doc.view)";
}

frappe.query_reports["Production and Planning Report RIGPL"] = {
	"filters": [
		{
			"fieldname":"view",
			"label": "View",
			"fieldtype": "Select",
			"options": "Production Planning\nPost Production Summary\nSO wise Summary\nOperation Time Analysis\nMachine Efficiency",
			"default": "Production Planning",
			"reqd": 1
		},
	    {
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 1,
			"depends_on": in_views(SUMMARY, OP_TIME, MACH_EFF),
			"default": frappe.datetime.get_today()
		},
	    {
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"reqd": 1,
			"depends_on": in_views(SUMMARY, OP_TIME, MACH_EFF),
			"default": frappe.datetime.get_today()
		},
	    {
			"fieldname":"operation",
			"label": "Operation",
			"fieldtype": "Link",
			"options": "Operation",
			"depends_on": in_views(PLANNING, OP_TIME)
		},
	    {
			"fieldname":"jc_status",
			"label": "Job Card Status",
			"fieldtype": "Select",
			"options": "\nOpen\nWork In Progress",
			"default": "Work In Progress",
			"depends_on": in_views(PLANNING)
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"depends_on": in_views(PLANNING, OP_TIME),
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_bm_query"}}
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"depends_on": in_views(PLANNING, OP_TIME),
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_tt_query"}}
		},
		{
			"fieldname":"spl",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"depends_on": in_views(PLANNING, OP_TIME),
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_spl_query"}}
		},
		{
			"fieldname":"series",
			"label": "Series",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"depends_on": in_views(PLANNING, OP_TIME),
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_series_query"}}
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"depends_on": in_views(PLANNING, OP_TIME, MACH_EFF),
			"get_query": function(){ return {'filters': [['Item', 'has_variants','=', 0]]}}
		},
		{
			"fieldname":"sales_order",
			"label": "Sales Order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"depends_on": in_views(PLANNING, SO_WISE, OP_TIME, MACH_EFF),
			"get_query": function(){ return {query: "rigpl_erpnext.manufacturing_rigpl.doctype.create_bulk_process_sheet." +
			    "create_bulk_process_sheet.get_so_pending_for_process_sheet"}}
		},
		{
			"fieldname":"mach_eff_type",
			"label": "Efficiency Type",
			"fieldtype": "Select",
			"options": "\nDaily\nTotal",
			"default": "Total",
			"depends_on": in_views(MACH_EFF)
		}
	],
	"formatter": rigpl_erpnext.report.blank_zero_formatter,
};
}
