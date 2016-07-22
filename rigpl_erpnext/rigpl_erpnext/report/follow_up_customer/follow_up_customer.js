// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Follow Up-Customer"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"options": "Customer",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -24),
		},
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname":"territory",
			"label": "Territory",
			"fieldtype": "Link",
			"options": "Territory"
		},
		{
			"fieldname":"sales_person",
			"label": "Sales Person",
			"fieldtype": "Link",
			"options": "Sales Person"
		},
		{
			"fieldname":"rating",
			"label": "Customer Rating",
			"fieldtype": "Select",
			"options": "\nOK\nBlack Listed\nChanged Business\nThrough Dealer\nTrial In Progress"
		},
		{
			"fieldname":"details",
			"label": "Details",
			"fieldtype": "Check",
			"default": 1
		}
	]
}
