frappe.query_reports["Stock Valuation"] = {
	"filters": [
		{
			"fieldname":"item_code",
			"label": "Item",
			"fieldtype": "Link",
			"options": "Item",
			"width": "50"
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Select",
			"options": "\nHSS\nCarbide",
			"width": "50"
		},
		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Quality",
			"width": "50"
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Tool Type",
			"width": "50"
		},
		{
			"fieldname":"is_rm",
			"label": "Is RM",
			"fieldtype": "Select",
			"options": "\nYes",
			"width": "50"
		},
		{
			"fieldname":"pl",
			"label": "Price List",
			"fieldtype": "Link",
			"options": "Price List",
			"width": "50"
		},
		{
			"fieldname":"warehouse",
			"label": "Warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": "50"
		},
		{
			"fieldname":"date",
			"label": "Valuation Date",
			"fieldtype": "Date",
			"width": "80",
			"default": frappe.datetime.get_today()
		}
	]
}