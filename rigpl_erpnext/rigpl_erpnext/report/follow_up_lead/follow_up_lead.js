// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Follow Up-Lead"] = {
	"filters": [
		{
			"fieldname":"lead",
			"label": "Lead",
			"fieldtype": "Link",
			"options": "Lead"
		},
		{
			"fieldname":"owner",
			"label": "Lead Owner",
			"fieldtype": "Link",
			"options": "User"
		},
		{
			"fieldname":"next_contact",
			"label": "Lead Next Contact",
			"fieldtype": "Link",
			"options": "User"
		},
		{
			"fieldname":"status",
			"label": "Status of Lead OR Customer",
			"fieldtype": "Select",
			"options": "\nHot\nCold\nQuotation Sent\nConverted\nLost\nTrial Passed\nTrial Failed"
		},
		{
			"fieldname":"territory",
			"label": "Territory",
			"fieldtype": "Link",
			"options": "Territory"
		},
		{
			"fieldname":"details",
			"label": "Details",
			"fieldtype": "Check",
			"default": 1
		}
	]
}
