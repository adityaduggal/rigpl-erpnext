// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Salary Structure"] = {
	"filters": [
		{
			"fieldname":"employee",
			"label": "Employee",
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
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), 12)
		},
		{
			"fieldname":"without_salary_structure",
			"label": "Emp w/o SS",
			"fieldtype": "Check"
		},
	]
}
