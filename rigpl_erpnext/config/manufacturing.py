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
					"name": "Items For Production",
					"doctype": "Production Order",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Pending So (Prd)",
					"doctype": "Production Order",
				},
			]
		}
		
	]
