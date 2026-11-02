// Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["RM Wastage Analysis"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today(),
		},
		{
			"fieldname": "group_by",
			"label": __("Group By"),
			"fieldtype": "Select",
			"options": "\nBOM Template\nFG Item\nRM Item",
		},
		{
			"fieldname": "bom_template",
			"label": __("BOM Template"),
			"fieldtype": "Link",
			"options": "BOM Template RIGPL",
		},
		{
			"fieldname": "over_limit_only",
			"label": __("Over Limit Only"),
			"fieldtype": "Check",
		},
		{
			"fieldname": "bypassed_only",
			"label": __("Bypassed Only"),
			"fieldtype": "Check",
		},
	],
	"formatter": rigpl_erpnext.report.blank_zero_formatter,
};
