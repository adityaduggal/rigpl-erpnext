// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Loan Analysis"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company Registered With"),
			"fieldtype": "Link",
			"options": "Letter Head"
		},		
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
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname":"view",
			"label": __("Show"),
			"fieldtype": "Select",
			"options": [
				"Employees with Existing Loans (Active Balances)",
				"Employees with Transactions in Period",
				"Details of 1 Employee",
			].join("\n"),
			"default": "Employees with Existing Loans (Active Balances)",
			"reqd": 1
		},
	],
	// A summary row of an employee who left on or before To Date and still has a Closing balance is red.
	// The same rule orders these rows first in the .py file.
	"formatter": function (value, row, column, data, default_formatter) {
		let html = rigpl_erpnext.report.blank_zero_formatter(value, row, column, data, default_formatter);
		if (column && column.fieldname === "pending_advances" && value) {
			// 1 link for each pending Employee Advance; the value is the names joined by ", "
			html = value.split(", ").map(name => frappe.utils.get_form_link("Employee Advance", name, true)).join(", ");
		}
		const to_date = frappe.query_report.get_filter_value("to_date");
		if (data && data.relieving_date && data.relieving_date <= to_date && flt(data.closing)) {
			return `<span style="color: red">${html}</span>`;
		}
		return html;
	},
}
