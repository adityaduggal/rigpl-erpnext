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
			"fieldname":"company",
			"label": __("GL Company"),
			"fieldtype": "Link",
			"options": "Company"
		},
		{
			"fieldname":"non_zero",
			"label": "Non Zero",
			"fieldtype": "Check",
			"default": 1
		},
	],
	// A row of an employee who left on or before To Date and still has a Closing balance is red.
	// The same rule orders these rows first in the .py file.
	"formatter": function (value, row, column, data, default_formatter) {
		const html = rigpl_erpnext.report.blank_zero_formatter(value, row, column, data, default_formatter);
		const to_date = frappe.query_report.get_filter_value("to_date");
		if (data && data.relieving_date && data.relieving_date <= to_date && flt(data.closing)) {
			return `<span style="color: red">${html}</span>`;
		}
		return html;
	},
}
