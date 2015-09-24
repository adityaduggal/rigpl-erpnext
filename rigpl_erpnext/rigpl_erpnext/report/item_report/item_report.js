frappe.query_reports["Item Report"] = {
	"filters": [
		{
			"fieldname":"rm",
			"label": "Is RM",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0
		},
		{
			"fieldname":"brand",
			"label": "Brand",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0
		},

		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0
		},
		{
			"fieldname":"spl_treatment",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname":"show_in_website",
			"label": "Show in Website",
			"fieldtype": "Check"
		},
		{
			"fieldname":"special",
			"label": "Check this to Bypass Validation",
			"fieldtype": "Check"
		}
	]
}
