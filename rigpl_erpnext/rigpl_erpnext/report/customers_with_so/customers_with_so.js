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
			"options": "Territory",
			"reqd" : 0
		},
		{
			"fieldname":"sales_person",
			"label": "Sales Person",
			"fieldtype": "Link",
			"options": "Sales Person",
			"reqd" : 0
		},
		{
			"fieldname":"sales_partner",
			"label": "Sales Partner",
			"fieldtype": "Link",
			"options": "Sales Partner",
			"reqd" : 0
		},
		{
			"fieldtype": "Break"
		},
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 1
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": get_today(),
			"reqd": 1
		}
	]
}
