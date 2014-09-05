frappe.query_reports["CForms Analysis"] = {
	"filters": [

		{
			"fieldname":"fiscal_year",
			"label": "Fiscal Year",
			"fieldtype": "Link",
			"options": "Fiscal Year"
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
			"options": "Received\nNot Received"
		},
		{
			"fieldname":"company",
			"label": "Company",
			"fieldtype": "Link",
			"options": "Letter Head"
		},
	]
}
