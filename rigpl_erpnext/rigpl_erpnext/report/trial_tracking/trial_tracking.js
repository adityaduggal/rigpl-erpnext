frappe.query_reports["Trial Tracking"] = {
	"filters": [
		{
			"fieldname":"trial_status",
			"label": "Trial Status",
			"fieldtype": "Select",
			"options": "In Production\nMaterial Ready\nAwaited\nPassed\nFailed",
			"reqd": 1
		},
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname":"trial_owner",
			"label": "Owner",
			"fieldtype": "Link",
			"options": "Sales Person"
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