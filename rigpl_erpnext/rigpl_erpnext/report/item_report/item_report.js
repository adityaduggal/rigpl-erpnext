frappe.query_reports["Item Report"] = {
	"filters": [
		{
			"fieldname":"brand",
			"label": "Brand",
			"fieldtype": "Link",
			"options": "Brand",
		},
		{
			"fieldname":"material",
			"label": "Material",
			"fieldtype": "Select",
			"options": "\nCarbide\nHSS",
			"reqd": 1
		},
		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Quality",
		},
		{
			"fieldname":"tool_type",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Tool Type",
			"reqd": 1
		},
		{
			"fieldname":"is_rm",
			"label": "Is RM",
			"fieldtype": "Select",
			"options": "\nYes",
		},
		{
			"fieldname":"show_in_website",
			"label": "Show in Website",
			"fieldtype": "Check"
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname":"special",
			"label": "Check this to Bypass Validation",
			"fieldtype": "Check"
		}
	]
}
