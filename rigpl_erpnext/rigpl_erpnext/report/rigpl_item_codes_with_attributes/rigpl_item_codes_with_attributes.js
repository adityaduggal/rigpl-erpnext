// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["RIGPL Item Codes with Attributes"] = {
	"filters": [
		{
			"fieldname":"template",
			"label": "Is Template",
			"fieldtype": "Check",
			"default": 1,
		},
		{
			"fieldname":"disabled",
			"label": "Include Disabled",
			"fieldtype": "Check",
			"default": 0,
		},
	]
}
