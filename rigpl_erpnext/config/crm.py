from frappe import _

def get_data():
	return [
		{
			"label": _("Communication"),
			"icon": "icon-star",
			"items": [
				{
					"type": "doctype",
					"name": "Sales Call Tool",
					"description": _("Tool to Add Communication and Reminders"),
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