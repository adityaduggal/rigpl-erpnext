// Copyright (c) 2016, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Production and Planning Report RIGPL"] = {
	"filters": [
	    {
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"required": 1,
			"default": frappe.datetime.get_today()
		},
	    {
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"required": 1,
			"default": frappe.datetime.get_today()
		},
	    {
			"fieldname":"operation",
			"label": "Operation",
			"fieldtype": "Link",
			"required": 0,
			"options": "Operation"
		},
		{
			"fieldname":"rm",
			"label": "Is RM",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_rm_query"}}
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
			"fieldname":"brand",
			"label": "Brand",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_brand_query"}}
		},

		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_quality_query"}}
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
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function(){ return {'filters': [['Item', 'has_variants','=', 0]]}}
		},
		{
			"fieldname":"summary",
			"label": "Post Production Summary",
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname":"production_planning",
			"label": "Production Planning",
			"fieldtype": "Check",
			"default": 0
		}
	]
};
