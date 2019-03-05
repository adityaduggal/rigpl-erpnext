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
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname":"territory",
			"label": "Territory",
			"fieldtype": "Link",
			"options": "Territory"
		},
		{
			"fieldname":"draft",
			"label": "Draft",
			"fieldtype": "Check"			
		},
		{
			"fieldname":"summary",
			"label": "Summary",
			"fieldtype": "Check",
			"default": 1
		},
	],
};
