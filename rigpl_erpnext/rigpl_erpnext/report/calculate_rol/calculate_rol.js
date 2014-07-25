frappe.query_reports["Calculate ROL"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date"
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": get_today()
		},
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
			"options": "\nYes"
		},
		{
			"fieldname":"base_material",
			"label": "Base Material",
			"fieldtype": "Select",
			"options": "HSS\nCarbide"
		},
		{
			"fieldname":"tool_type",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Tool Type"
		},
		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Quality"
		}
	]
}
