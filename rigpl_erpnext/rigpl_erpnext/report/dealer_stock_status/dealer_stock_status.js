// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Dealer Stock Status"] = {
	"filters": [
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 1,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_bm_query"}}
		},
		{
			"fieldname":"series",
			"label": "Series",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_series_query"}}
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_tt_query"}}
		},
		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_quality_query"}}
		},
		{
			"fieldname":"spl",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_spl_query"}}
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function(){ return {'filters': [['Item', 'has_variants','=', 0]]}}
		},
		{
			"fieldtype": "Break",
		},
		{
			"fieldname":"rol_sort",
			"label": "Sort By ROL",
			"fieldtype": "Check",
		},
		{
			"fieldname":"dead_stock",
			"label": "Dead Stock",
			"fieldtype": "Check",
		},
		{
			"fieldname":"min_rol",
			"label": "Minimum ROL",
			"fieldtype": "Int",
			"default": 10,
		},
		{
			"fieldname":"max_rol",
			"label": "Maximum ROL",
			"fieldtype": "Int",
		}
	]
}
