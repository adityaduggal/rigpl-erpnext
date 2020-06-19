from frappe import _

def get_data():
	return [
		{
			"label": _("Production"),
			"icon": "icon-paper-clip",
			"items": [
				{
					"type": "doctype",
					"name": "Important Documents",
					"description": _("List of all Standards and Drawings"),
				}
			]
		},
		{
			"label": _("Tools"),
			"icon": "icon-paper-clip",
			"items": [
				{
					"type": "doctype",
					"name": "Create Bulk Production Orders",
					"description": _("Utility to Create Bulk Production or Work Orders"),
				}
			]
		},
		{
			"label": _("Rohit Reports"),
			"icon": "icon-paper-clip",
			"items": [
				{
					"type": "report",
					"is_query_report": True,
					"name": "Items For Production",
					"doctype": "Work Order",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Pending Production Orders",
					"doctype": "Work Order",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Pending So (Prd)",
					"doctype": "Work Order",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Standards and Drawings RIGPL",
					"doctype": "Important Documents",
				},
			]
		}
		
	]
