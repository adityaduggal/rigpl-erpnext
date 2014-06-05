from frappe import _

def get_data():
	return [
		{
			"label": _("Rohit Reports"),
			"icon": "icon-paper-clip",
			"items": [
				{
					"type": "report",
					"is_query_report": True,
					"name": "Calculate ROL",
					"doctype": "Stock Ledger Entry",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Stock Ledger Normal",
					"doctype": "Stock Ledger Entry",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Stock Valuation",
					"doctype": "Stock Entry Detail",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Value Addition",
					"doctype": "Tool Type",
				},
			]
		}
	]
