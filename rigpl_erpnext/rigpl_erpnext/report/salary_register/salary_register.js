// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Salary Register"] = {
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
			"fieldname":"salary_mode",
			"label": "Salary Mode",
			"fieldtype": "Select",
			"options": "\nBank\nCash\nCheque",
		},
		{
			"fieldname":"without_salary_slip",
			"label": "Emp w/o SS",
			"fieldtype": "Check"
		},
		{
			"fieldname":"bank_only",
			"label": "Bank Only",
			"fieldtype": "Check"
		},
		{
			"fieldname":"summary",
			"label": "Summary",
			"fieldtype": "Check"
		},
	]
}
