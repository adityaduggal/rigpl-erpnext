frappe.query_reports["Calculate ROL"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 1,
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": get_today(),
			"reqd": 1,
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname":"is_rm",
			"label": "RM",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','=','Is RM']]}}
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 1,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','=','Base Material']]}}
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
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','LIKE','%Quality']]}}
		},
		{
			"fieldname":"spl",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','=','Special Treatment']]}}
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 
			'parent','=','Tool Type']]}}
		}
	]
}
