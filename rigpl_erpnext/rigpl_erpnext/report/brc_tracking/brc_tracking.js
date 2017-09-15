// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["BRC Tracking"] = {
	"filters": [
		{
			"fieldname":"ref_name",
			"label": "Sales Invoice of Purchase Invoice No",
			"fieldtype": "Data",
			"reqd": 0
		},
		{
			"fieldname":"shb_no",
			"label": "Shipping Bill Number",
			"fieldtype": "Data",
			"reqd": 0
		},
		{
			"fieldname":"brc_no",
			"label": "BRC Number",
			"fieldtype": "Data",
			"reqd": 0
		},
		{
			"fieldname":"type",
			"label": "Export or Import",
			"fieldtype": "Select",
			"options": "\nExport\nImport"
		},
		{
			"fieldname":"brc_status",
			"label": "BRC Status",
			"fieldtype": "Select",
			"options": "\nBRC Pending\nBRC Issued"
		},

	]
}
