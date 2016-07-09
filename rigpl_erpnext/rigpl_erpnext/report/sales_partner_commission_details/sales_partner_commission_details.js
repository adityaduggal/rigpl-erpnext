// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Sales Partner Commission Details"] = {
	"filters": [
		{
			"fieldname":"doc_type",
			"label": "Transaction Type",
			"fieldtype": "Select",
			"options": "\nSales Order\nDelivery Note\nSales Invoice",
			"reqd": 1
		},
		{
			"fieldname":"based_on",
			"label": "Based On",
			"fieldtype": "Select",
			"options": "\nMaster\nTransaction",
			"reqd": 1
		},
		{
			"fieldname":"sales_partner",
			"label": "Sales Partner",
			"fieldtype": "Link",
			"options": "Sales Partner"
		},
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname":"territory",
			"label": "Territory",
			"fieldtype": "Link",
			"options": "Territory"
		},
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"default": frappe.defaults.get_user_default("year_start_date")
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": get_today()
		}
	]
}
