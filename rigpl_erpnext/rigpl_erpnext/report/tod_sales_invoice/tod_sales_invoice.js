frappe.query_reports["TOD Sales Invoice"] = {
	"filters": [

		{
			"fieldname":"fiscal_year",
			"label": "Fiscal Year",
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"reqd": 1,
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
			"fieldtype": "Date"
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date"
		},
		{
			"fieldname":"summary",
			"label": "Summary",
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname":"separated_tod",
			"label": "TOD Yes No",
			"fieldtype": "Check",
			"default": 1
		},
	]
}
