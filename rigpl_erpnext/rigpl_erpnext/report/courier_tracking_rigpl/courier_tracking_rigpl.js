// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Courier Tracking RIGPL"] = {
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
			"fieldname":"from_address",
			"label": "From Address",
			"fieldtype": "Link",
			"options": "Address",
			"get_query": function(){ return {'filters': [['Address', 'is_your_company_address','=', 1]]}}
		},
		{
			"fieldname":"transporter",
			"label": "Transporter",
			"fieldtype": "Link",
			"options": "Transporters",
			"get_query": function(){ return {'filters': [['Transporters', 'track_on_shipway','=', 1]]}}
		},
		{
			"fieldname":"status",
			"label": "Status",
			"fieldtype": "Select",
			"options": "\nDelivered\nNot Delivered\nNo Information\nIn Transit\nCancelled"
		},
		{
			"fieldname":"awb_no",
			"label": "AWB No",
			"fieldtype": "Data",
		},
		{
			"fieldname":"document_name",
			"label": "Document Name",
			"fieldtype": "Data",
		},
		{
			"fieldname":"receiver_name",
			"label": "Receiver Name",
			"fieldtype": "Data",
		},
		{
			"fieldtype": "Break"
		},
		{
			"fieldname":"total_awb_by_transporter",
			"label": "Total AWB Report",
			"fieldtype": "Check",
			"default": 0,
		},
		{
			"fieldname":"avg_delivery_times",
			"label": "Avg Delivery Time Report",
			"fieldtype": "Check",
			"default": 0,
		},
		{
			"fieldname":"detailed_report",
			"label": "Detailed Report",
			"fieldtype": "Check",
			"default": 0,
		},
		{
			"fieldname":"pending_exceptions",
			"label": "Pending Exception Report",
			"fieldtype": "Check",
			"default": 1,
		},
		{
			"fieldname":"old_exception",
			"label": "Old Exception Report",
			"fieldtype": "Check",
			"default": 0,
		},
	]
}
