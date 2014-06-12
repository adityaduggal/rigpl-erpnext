frappe.query_reports["Price List"] = {
	"filters": [
		{
			"fieldname":"price_list",
			"label": "Price List",
			"fieldtype": "Link",
			"options": "Price List",
			"default": "PL47"
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Tool Type"
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Select",
			"options": "\nCarbide\nHSS"
		},
		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Quality"
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item"
		}
	]
}
