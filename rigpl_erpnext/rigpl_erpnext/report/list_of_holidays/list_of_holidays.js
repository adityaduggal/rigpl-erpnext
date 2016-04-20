// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["List of Holidays"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.year_start()
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.year_end()
		},
		{
			"fieldname":"name",
			"label": __("Holiday List"),
			"fieldtype": "Link",
			"options": "Holiday List",
			"reqd":1,
		}
	]
}
