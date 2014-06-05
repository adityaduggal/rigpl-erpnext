frappe.query_reports["Stock Ledger Normal"] = {
	"filters": [
		{
			"fieldname":"item",
			"label": "Item",
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname":"warehouse",
			"label": "Warehouse",
			"fieldtype": "Link",
			"options": "Warehouse"
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