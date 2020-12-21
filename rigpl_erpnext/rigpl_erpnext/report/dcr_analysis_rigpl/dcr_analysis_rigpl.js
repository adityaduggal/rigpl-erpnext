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
			"get_query": function() {
				return {
					"filters": {
						"name": ["in", "Customer, Lead"],
					}
				}
			}
		},
		{
			"fieldname":"docname",
			"label": "Name of Lead or Customer",
			"fieldtype": "Dynamic Link",
			"get_options": function() {
				let document = frappe.query_report.get_filter_value('document');
				if(!document) {
					frappe.throw(__("Please Select Customer or Lead"));
				}
				return document;
			}
		},
		{
			"fieldname":"owner",
			"label": "User ID of Owner",
			"fieldtype": "Link",
			"options": "User",
			"reqd" : 0
		},
		{
			"fieldname":"territory",
			"label": "Territory",
			"fieldtype": "Link",
			"options": "Territory",
			"reqd" : 0
		},
		{
			"fieldtype": "Break"
		},
		{
			"fieldname":"analysis_summary",
			"label": "Analysis Summary",
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname":"comm_summary",
			"label": "Communication Summary",
			"fieldtype": "Check",
			"default": 0
		},
		{
			"fieldname":"comm_details",
			"label": "Communication Details",
			"fieldtype": "Check",
			"default": 0
		}
	]
}
