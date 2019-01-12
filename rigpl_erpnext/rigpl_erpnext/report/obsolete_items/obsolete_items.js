// Copyright (c) 2013, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Obsolete Items"] = {
	"filters": [
		{
			"fieldname":"eol",
			"label": "End Of Life",
			"fieldtype": "Date",
			"default" : frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname":"is_rm",
			"label": "RM",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_rm_query"}}
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 1,
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
			"fieldname":"spl",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_spl_query"}}
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
			"fieldname":"item",
			"label": "Item",
			"fieldtype": "Link",
			"options": "Item",
			"reqd": 0
		},
		{
			"fieldname":"has_variants",
			"label": "Has Variants",
			"fieldtype": "Check",
			"default" : 0
		},
		{
			"fieldname":"web",
			"label": "Web",
			"fieldtype": "Check",
			"default" : 0
		},
		{
			"fieldname":"is_pl_item",
			"label": "PL Item",
			"fieldtype": "Check",
			"default" : 1
		}
	]
}
