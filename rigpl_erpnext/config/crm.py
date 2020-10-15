from frappe import _

def get_data():
	return [
		{
			"label": _("Sales Pipeline"),
			"items": [
				{
					"type": "doctype",
					"name": "Daily Call",
				},
			]
		},
        {
            "label": _("Settings"),
            "items": [
                {
                    "type": "doctype",
                    "name": "IndiaMart Pull Leads",
                },
            ]
        },
		{
			"label": _("Reports"),
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
				},
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Follow Up",
                    "doctype": "Customer",
                },
			]
		}
	]