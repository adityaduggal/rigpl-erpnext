frappe.query_reports["VA Sale Invoice"] = {
	"filters": [

		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"default": get_today()-30
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": get_today()
		}

	]
}
