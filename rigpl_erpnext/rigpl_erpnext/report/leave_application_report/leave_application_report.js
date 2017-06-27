// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Leave Application Report"] = {
	"filters": [
		{
			"fieldname":"employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee"
		},
		{
			"fieldname":"branch",
			"label": __("Branch"),
			"fieldtype": "Link",
			"options": "Branch"
		},
		{
			"fieldname":"department",
			"label": __("Department"),
			"fieldtype": "Link",
			"options": "Department"
		},
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date"
		},
		{
			"fieldname":"status",
			"label": "Status",
			"fieldtype": "Select",
			"options": "\nApproved\nRejected\nOpen"
		},
	]
}
