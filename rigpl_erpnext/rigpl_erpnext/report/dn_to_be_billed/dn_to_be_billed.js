frappe.query_reports["DN To Be Billed"] = {
	"filters": [
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
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
		},
		{
			"fieldname":"draft",
			"label": "Consider Draft Invoices",
			"fieldtype": "Select",
			"options": "Yes\nNo"
		},
		{
			"fieldname":"trial",
			"label": "Trial",
			"fieldtype": "Select",
			"options": "No\nYes"
		},
	]
}
