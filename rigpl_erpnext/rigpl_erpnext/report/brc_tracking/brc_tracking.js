// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["BRC Tracking"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": "SB From Date",
			"fieldtype": "Date",
			"reqd": 0
		},
		{
			"fieldname":"to_date",
			"label": "SB To Date",
			"fieldtype": "Date",
			"reqd": 0
		},
		{
			"fieldname":"brc_status",
			"label": "BRC Status",
			"fieldtype": "Select",
			"options": "\nBRC Pending\nBRC Issued\nOFAC"
		},
		{
			"fieldname":"meis_status",
			"label": "MEIS Status",
			"fieldtype": "Select",
			"options": "\nAll MEIS\nMEIS Pending\nMEIS Claimed\nMEIS Expired\nMEIS Not Applicable"
		},
		{
			"fieldname":"docstatus",
			"label": "Document Status",
			"fieldtype": "Select",
			"options": "\nDraft\nSubmitted"
		},

	]
}
