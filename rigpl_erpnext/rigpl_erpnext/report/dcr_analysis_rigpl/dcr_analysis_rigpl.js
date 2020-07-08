// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["DCR Analysis RIGPL"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
		},
		{
			"fieldname":"document",
			"label": "Lead or Customer",
			"fieldtype": "Link",
			"options": "DocType",
			"reqd" : 0
		},
		{
			"fieldname":"docname",
			"label": "Name of Lead or Customer",
			"fieldtype": "Dynamic Link",
			"options": "document",
			"reqd" : 0
		},
		{
			"fieldtype": "Break"
		},
		{
			"fieldname":"analysis_summary",
			"label": "Analysis Summary",
			"fieldtype": "Check",
			"default": 0
		},
		{
			"fieldname":"analysis_details",
			"label": "Analysis Details",
			"fieldtype": "Check",
			"default": 0
		},
		{
			"fieldname":"comm_summary",
			"label": "Communication Summary",
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname":"comm_details",
			"label": "Communication Details",
			"fieldtype": "Check",
			"default": 0
		}
	]
}
