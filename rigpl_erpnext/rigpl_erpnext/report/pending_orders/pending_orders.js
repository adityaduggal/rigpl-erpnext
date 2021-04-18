frappe.query_reports["Pending Orders"] = {
	"filters": [
		{
			"fieldname":"stock_status",
			"label": "Stock Items with Stock Status",
			"fieldtype": "Check"
		},
		{
			"fieldname":"made_to_order",
			"label": "Made to Order Status",
			"fieldtype": "Check"
		},
		{
			"fieldname":"bm",
			"label": "Base Material",
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"reqd": 0,
			"ignore_link_validation": true,
			"get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_bm_query"}}
		},
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname":"item",
			"label": "Item",
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname":"date",
			"label": "SO Upto Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		}
	]
}
