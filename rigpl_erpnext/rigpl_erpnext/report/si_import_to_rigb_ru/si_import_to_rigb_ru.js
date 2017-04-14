// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["SI Import to RIGB RU"] = {
	"filters": [
		{
			"fieldname":"id",
			"label": "Sales Invoice Number",
			"fieldtype": "Link",
			"reqd": 1,
			"options": "Sales Invoice",
			"get_query": function(){ return {'filters': [['Sales Invoice', 'docstatus','=',1]]}}
		}
	]
}
