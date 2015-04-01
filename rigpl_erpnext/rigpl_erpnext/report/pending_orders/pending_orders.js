frappe.query_reports["Pending Orders"] = {
	"filters": [

		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname":"item",
			"label": "Item",
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname":"date",
			"label": "SO Upto Date",
			"fieldtype": "Date",
			"default": get_today()
		}
	]
}