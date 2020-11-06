// Copyright (c) 2016, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Process Sheet Analysis"] = {
	"filters": [
		{
			"fieldname":"status",
			"label": "Status",
			"fieldtype": "Select",
			"options": "\nCancelled\nCompleted\nDraft\nIn Progress\nShort Closed\nStopped\nSubmitted"
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
		}
	]
};
