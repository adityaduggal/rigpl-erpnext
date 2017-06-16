// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Employee Balances RIGPL"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.month_end(frappe.datetime.get_today()),
		},
		{
			"fieldname":"employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee"
		},
		{
			"fieldname":"branch",
			"label": "Branch",
			"fieldtype": "Link",
			"options": "Branch"
		},
		{
			"fieldname":"department",
			"label": "Department",
			"fieldtype": "Link",
			"options": "Department"
		},
		{
			"fieldname":"designation",
			"label": "Designation",
			"fieldtype": "Link",
			"options": "Designation"
		},
		{
			"fieldname":"company_registered_with",
			"label": "Company",
			"fieldtype": "Link",
			"options": "Letter Head"
		},
		{
			"fieldname":"non_zero",
			"label": "Non Zero",
			"fieldtype": "Check",
			"default": 1
		},
	]
}
