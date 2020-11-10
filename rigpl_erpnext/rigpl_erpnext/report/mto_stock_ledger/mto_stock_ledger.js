// Copyright (c) 2016, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["MTO Stock Ledger"] = {
	"filters": [
		{
			"fieldname":"so_item",
			"label": "Sales Order Item",
			"fieldtype": "Data",
			"reqd": 1
		},
		{
			"fieldname":"warehouse",
			"label": "Warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"reqd": 1
		},
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 0,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"reqd": 0,
			"default": frappe.datetime.get_today()
		}
	]
};
