frappe.query_reports["Item Report"] = {
	"filters": [
		{
			"fieldname":"brand",
			"label": "Brand",
			"fieldtype": "Link",
			"options": "Brand",
			"default": "Rohit"
		},
		{
			"fieldname":"material",
			"label": "Material",
			"fieldtype": "Select",
			"options": "\nCarbide\nHSS",
			"default": "HSS"
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
			"options": "Tool Type"
		},
		{
			"fieldname":"is_rm",
			"label": "Is RM",
			"fieldtype": "Select",
			"options": "\nYes\nNo",
			"default": "No"
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
			"label": "",
			"fieldtype": "Check"
		}
	]
}
