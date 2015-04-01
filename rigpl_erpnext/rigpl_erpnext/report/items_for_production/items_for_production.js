frappe.query_reports["Items For Production"] = {
	"filters": [
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname":"is_rm",
			"label": "Is RM",
			"fieldtype": "Select",
			"options": "\nYes\nNo"
		},
		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Quality"
		},
		{
			"fieldname":"tool_type",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Tool Type"
		},
		{
			"fieldname":"brand",
			"label": "Brand",
			"fieldtype": "Link",
			"options": "Brand"
		},
		{
			"fieldname":"special_treatment",
			"label": "Special Treatment",
			"fieldtype": "Select",
			"options": "\nACX\nCRY\nHard\nNone\nTiAlN\nTiN"
		}
	]
}
