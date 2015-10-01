frappe.query_reports["Price List"] = {
	"filters": [
		{
			"fieldname":"pl",
			"label": "Price List",
			"fieldtype": "Link",
			"options": "Price List",
			"default": "PL47",
			"reqd": 1,
			"get_query": function(){ return {'filters': [['Price List', 'enabled','=',1]]}}
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
			"reqd": 0,
			"get_query": function(){ return {'filters': [['Item Attribute Value', 'parent','=','Tool Type']]}}
		},
		{
			"fieldname":"spl",
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
			"options": "Item"
		},
		{
			"fieldname":"is_pl",
			"label": "Is PL",
			"fieldtype": "Check"
		}
	]
}
