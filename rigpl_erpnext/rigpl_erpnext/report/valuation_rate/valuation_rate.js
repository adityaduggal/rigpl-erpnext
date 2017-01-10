// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Valuation Rate"] = {
	"filters": [
		{
			"fieldname":"pl",
			"label": "Price List",
			"fieldtype": "Link",
			"options": "Price List",
			"default": "PL47",
			"reqd": 1,
			"get_query": function(){ return {'filters': [['Price List', 'enabled','=',1]]}}
		},
		{
			"fieldname":"rm",
			"label": "Is RM",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_rm_query"}}
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 1,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_bm_query"}}
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 1,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_tt_query"}}
		},
		{
			"fieldname":"series",
			"label": "Series",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_series_query"}}
		},
		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_quality_query"}}
		},
		{
			"fieldname":"spl",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_spl_query"}}
		},
		{
			"fieldname":"purpose",
			"label": "Purpose",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_purpose_query"}}
		},
		{
			"fieldname":"type",
			"label": "Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_type_query"}}
		},
		{
			"fieldname":"mtm",
			"label": "Material to Machine",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_mtm_query"}}
		},
		{
			"fieldname":"eol",
			"label": "End Of Life",
			"fieldtype": "Date",
			"default": get_today(),
			"reqd": 1
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function(){ return {'filters': [['Item', 'has_variants','=', 0]]}}
		},
		{
			"fieldname":"variant_of",
			"label": "Variant Of",
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function(){ return {'filters': [['Item', 'has_variants','=', 1]]}}
		}
	]
}
