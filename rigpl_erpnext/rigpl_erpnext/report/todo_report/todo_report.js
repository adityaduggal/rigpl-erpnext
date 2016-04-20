// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["ToDo Report"] = {
	"filters": [
		{
			"fieldname":"owner",
			"label": "Owner",
			"fieldtype": "Link",
			"options": "User"
		},
		{
			"fieldname":"assigned_by",
			"label": "Assigned By",
			"fieldtype": "Link",
			"options": "User"
		},
		{
			"fieldname":"status",
			"label": "Status",
			"fieldtype": "Select",
			"options": "\nOpen\nClosed",
			"reqd": 1,
			"default": "Open"
		},
		{
			"fieldname":"summary",
			"label": "Summary",
			"fieldtype": "Check",
			"default": 0
		},
	]
}
