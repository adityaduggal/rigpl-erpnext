// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Pending Purchase Orders"] = {
	"filters": [
		{
			"fieldname":"subcontracting",
			"label": "Is Job Work",
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function(){ return {'filters': [['Item', 'is_purchase_item','=', 1]]}}
		},
		{
			"fieldname":"supplier",
			"label": "Supplier",
			"fieldtype": "Link",
			"options": "Supplier"
		},
		{
			"fieldname":"date",
			"label": "PO Upto Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
	]
}
