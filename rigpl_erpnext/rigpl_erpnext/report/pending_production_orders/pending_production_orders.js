// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Pending Production Orders"] = {
	"filters": [
		{
			"fieldname":"so_id",
			"label": "Sales Order Number",
			"fieldtype": "Link",
			"options": "Sales Order",
			"get_query": function(){ return {'filters': [['Sales Order', 'docstatus','=', 1]]}, {'filters': [['Sales Order', 'status','!=', "To Bill"]]}, {'filters': [['Sales Order', 'status','!=', "Completed"]]}, {'filters': [['Sales Order', 'status','!=', "Closed"]]}}
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function(){ return {'filters': [['Item', 'is_sales_item','=', 1]]}}
		},
		{
			"fieldname":"warehouse",
			"label": "Warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"get_query": function(){ return {'filters': [['Warehouse', 'disabled', '=', 0]]}}
		},
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date"
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": get_today()
		},
	]
}
