frappe.query_reports["Price List"] = {
	"filters": [
		{
			"fieldname":"price_list",
			"label": "Price List",
			"fieldtype": "Link",
			"options": "Price List",
			"default": "PL47",
			"reqd": 1
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Tool Type",
			"reqd": 1
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Select",
			"options": "\nCarbide\nHSS",
			"reqd": 1
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
