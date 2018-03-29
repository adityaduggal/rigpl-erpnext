from frappe import _

def get_data():
	return [
		{
			"label": _("Communication"),
			"icon": "icon-star",
			"items": [
				{
					"type": "doctype",
					"name": "Daily Call",
					"description": _("List of Daily Call and Visit Summary"),
				},
			]
		},
		{
			"label": _("Rohit Reports"),
			"icon": "icon-paper-clip",
			"items": [
				{
					"type": "report",
					"is_query_report": True,
					"name": "Follow Up-Customer",
					"doctype": "Customer",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Follow Up-Lead",
					"doctype": "Lead",
				}
			]
		}
	]