frappe.query_reports["CForms Analysis"] = {
	"filters": [

		{
			"fieldname":"fiscal_year",
			"label": "Fiscal Year",
			"fieldtype": "Link",
			"options": "Fiscal Year"
		},
		{
			"fieldname":"quarter",
			"label": "Quarter",
			"fieldtype": "Select",
			"options": "\nQ1\nQ2\nQ3\nQ4"
		},
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname":"status",
			"label": "Status",
			"fieldtype": "Select",
			"options": "Not Received\nReceived"
		},
		{
			"fieldname":"letter_head",
			"label": "Letter Head",
			"fieldtype": "Link",
			"options": "Letter Head"
		},
		{
			"fieldname":"date",
			"label": "C-Forms upto this Date",
			"fieldtype": "Date"
		},
		{
			"fieldname":"summary",
			"label": "Summary",
			"fieldtype": "Check"
		},
	]
}
