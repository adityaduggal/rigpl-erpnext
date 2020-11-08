// Copyright (c) 2016, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Customer Rating"] = {
	"filters": [
		{
			"fieldname":"years",
			"label": "Years",
			"fieldtype": "Int",
			"reqd": 1,
			"default": 5,
		},
		{
			"fieldname":"first_order",
			"label": "1st Order Value",
			"fieldtype": "Int",
			"reqd": 1,
			"default": 10000,
		},
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -60),
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today(),
		},
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer",
			"reqd": 0,
		},
		{
			"fieldname":"group",
			"label": "Customer Group",
			"fieldtype": "Link",
			"options": "Customer Group",
			"reqd": 0,
		},
		{
			"fieldname":"territory",
			"label": "Territory",
			"fieldtype": "Link",
			"options": "Territory",
			"reqd": 0,
		},
	]
};
