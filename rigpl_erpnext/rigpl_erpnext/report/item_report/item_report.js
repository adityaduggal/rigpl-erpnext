frappe.query_reports["Item Report"] = {
	"filters": [
		{
			"fieldname":"rm",
			"label": "Is RM",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"get_query": function(){ return {'filters': [['Item Attribute Value', 'parent','=','Is RM']]}}
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 1,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 'parent','=','Base Material']]}}
		},
		{
			"fieldname":"brand",
			"label": "Brand",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 'parent','=','Brand']]}}
		},

		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 'parent','Like','% Quality']]}}
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 1,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 'parent','=','Tool Type']]}}
		},
		{
			"fieldname":"spl_treatment",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 'parent','=','Special Treatment']]}}
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"reqd": 0
		},
		{
			"fieldname":"variant_of",
			"label": "Variant Of",
			"fieldtype": "Link",
			"options": "Item",
			"reqd": 0
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
