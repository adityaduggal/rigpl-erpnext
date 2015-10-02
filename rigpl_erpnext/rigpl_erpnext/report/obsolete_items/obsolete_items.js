// Copyright (c) 2013, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Obsolete Items"] = {
	"filters": [
		{
			"fieldname":"eol",
			"label": "End Of Life",
			"fieldtype": "Date",
			"default" : get_today(),
			"reqd": 1
		},
		{
			"fieldname":"is_rm",
			"label": "RM",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','=','Is RM']]}}
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 1,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','=','Base Material']]}}
		},
		{
			"fieldname":"brand",
			"label": "Brand",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 'parent','=','Brand']]}}
		},
		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','LIKE','%Quality']]}}
		},
		{
			"fieldname":"spl",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','=','Special Treatment']]}}
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','=','Tool Type']]}}
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
