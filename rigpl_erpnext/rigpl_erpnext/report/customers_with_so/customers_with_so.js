frappe.query_reports["Customers with SO"] = {
	"filters": [
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
			"fieldname":"sales_person",
			"label": "Sales Person",
			"fieldtype": "Link",
			"options": "Sales Person"
		},
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date"
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": get_today()
		}
	]
}
