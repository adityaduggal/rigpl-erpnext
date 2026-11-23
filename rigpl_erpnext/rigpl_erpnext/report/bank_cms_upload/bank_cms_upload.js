// Copyright (c) 2021, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
/* eslint-disable */

// The same numbers as DEFAULT_MAX_DAYS and USER_MAX_DAYS in bank_cms_upload.py. The server checks them again.
const DEFAULT_MAX_DAYS = 10;
const USER_MAX_DAYS = 30;

// If the period is longer than Max Days or the wrong way round, the date that was not changed moves
// (the To Date when From Date changed, the From Date when To Date changed). Then the report refreshes once.
function keep_period_within_limit(report, changed) {
	const max_days = cint(report.get_filter_value("max_days")) || DEFAULT_MAX_DAYS;
	const from_date = report.get_filter_value("from_date");
	const to_date = report.get_filter_value("to_date");
	const days = frappe.datetime.get_diff(to_date, from_date);
	if (!from_date || !to_date || (days >= 0 && days <= max_days)) {
		report.refresh(true);
	} else if (changed === "from_date") {
		report.set_filter_value("to_date", frappe.datetime.add_days(from_date, max_days));
	} else {
		report.set_filter_value("from_date", frappe.datetime.add_days(to_date, -max_days));
	}
}

// Only a System Manager can set Max Days above USER_MAX_DAYS
function check_max_days(report) {
	const max_days = cint(report.get_filter_value("max_days"));
	if (max_days < 1) {
		report.set_filter_value("max_days", DEFAULT_MAX_DAYS);
	} else if (max_days > USER_MAX_DAYS && !frappe.user.has_role("System Manager")) {
		frappe.msgprint(__("Only a System Manager can set Max Days above {0}", [USER_MAX_DAYS]));
		report.set_filter_value("max_days", USER_MAX_DAYS);
	} else {
		keep_period_within_limit(report, "from_date");
	}
}

frappe.query_reports["Bank CMS Upload"] = {
	// The Employee Advance link opens in a new window
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "employee_advance" && value) {
			value = value.replace("<a ", "<a target='_blank' ");
		}
		return value;
	},
	"filters": [
		{
			"fieldname":"entry_type",
			"label": "Entry Type",
			"fieldtype": "Select",
			"options": "\nEmployee Advance\nPayment Entry",
			"default": "Payment Entry",
			"reqd": 1,
		},
		{
			"fieldname":"payment_type",
			"label": "Payment Type",
			"fieldtype": "Select",
			"options": "Internal Transfer\nPay\nReceive",
			"default": "Pay",
			"reqd": 1,
		},
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), -DEFAULT_MAX_DAYS),
			"reqd": 1,
			"on_change": (report) => keep_period_within_limit(report, "from_date"),
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
			"on_change": (report) => keep_period_within_limit(report, "to_date"),
		},
		{
			"fieldname":"max_days",
			"label": "Max Days",
			"fieldtype": "Int",
			"default": DEFAULT_MAX_DAYS,
			"description": "Longest period of the report. Above " + USER_MAX_DAYS + " days only a System Manager can set it",
			"reqd": 1,
			"on_change": (report) => check_max_days(report),
		},
		{
			"fieldname":"status",
			"label": "Status",
			"fieldtype": "Select",
			"options": "\nDraft\nSubmitted\nCancelled",
			"default": "Draft",
			"reqd": 1,
		}
	]
};
