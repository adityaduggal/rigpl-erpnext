// Copyright (c) 2021, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Bank CMS Upload"] = {
	"filters": [
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
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), -1),
			"reqd": 1,
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
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
