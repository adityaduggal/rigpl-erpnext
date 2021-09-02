frappe.query_reports["Calculate ROL"] = {
	"filters": [
		{
			"fieldname":"months",
			"label": "Period",
			"fieldtype": "Data",
			"reqd": 1,
			"default": "12,15,18,21,24",
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
		},
		{
			"fieldname":"item",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"reqd": 1,
			"get_query": function(){ return {'filters': [['Item', 'has_variants','=', 0]]}}
		}
	]
}
