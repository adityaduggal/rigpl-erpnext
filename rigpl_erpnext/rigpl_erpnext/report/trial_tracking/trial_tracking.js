frappe.query_reports["Trial Tracking"] = {
	"filters": [
		{
			"fieldname":"trial_status",
			"label": "Trial Status",
			"fieldtype": "Select",
			"options": "Approved\nRejected\nAwaited"
		},
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": get_today()
		}
	]
}