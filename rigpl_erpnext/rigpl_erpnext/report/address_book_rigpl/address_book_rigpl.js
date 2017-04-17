// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Address Book RIGPL"] = {
	"filters": [
		{
			"fieldname":"type",
			"label": "type",
			"fieldtype": "Select",
			"options": "\nOnly Addresses\nOnly Contacts",
			"reqd": 1,
			"default": "Only Contacts",
		},
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer",
			"reqd": 0,
		},
		{
			"fieldname":"territory",
			"label": "Territory",
			"fieldtype": "Link",
			"options": "Territory",
			"reqd": 0,
		},
		{
			"fieldname":"customer_group",
			"label": "Customer Group",
			"fieldtype": "Link",
			"options": "Customer Group",
			"reqd": 0,
		},
		{
			"fieldname":"customer_type",
			"label": "Customer Type",
			"fieldtype": "Select",
			"options": "\nCompany\nIndividual",
			"reqd": 0,
		},
	]
}
