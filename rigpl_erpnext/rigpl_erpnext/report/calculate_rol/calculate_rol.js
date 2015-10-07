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
			"options": "Item",
			"get_query": function(){ return {'filters': [['Item', 'has_variants','=', 0]]}}
		},
		{
			"fieldname":"is_rm",
			"label": "RM",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_rm_query"}}
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 1,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_bm_query"}}
		},
		{
			"fieldname":"brand",
			"label": "Brand",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_brand_query"}}
		},
		{
			"fieldname":"quality",
			"label": "Quality",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_quality_query"}}
		},
		{
			"fieldname":"spl",
			"label": "Special Treatment",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_spl_query"}}
		},
		{
			"fieldname":"tt",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"get_query": function(){ return {query: "rigpl_erpnext.rigpl_erpnext.item.attribute_tt_query"}}
		}
	]
}
