// Copyright (c) 2013, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Template Variant Import Format"] = {
	"filters": [
		{
			"fieldname":"eol",
			"label": "End Of Life",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname":"variant_of",
			"label": "Variant Of",
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function(){ return {'filters': [['Item', 'has_variants','=', 1]]}}
		},
		{
			"fieldname":"show_in_website",
			"label": "Show in Website",
			"fieldtype": "Check"
		},
		{
			"fieldname":"template",
			"label": "Is Template",
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname":"restrictions",
			"label": "Restrictions",
			"fieldtype": "Check"
		}
	]
}
