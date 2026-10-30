frappe.query_reports["Pending Orders With Stock Status"] = {
	"filters": [
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname":"item",
			"label": "Item",
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname":"date",
			"label": "SO Upto Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		}
	],
	"formatter": rigpl_erpnext.report.blank_zero_formatter
}
