from frappe import _

def get_data():
	return [
		{
			"label": _("Setup"),
			"icon": "icon-gear",
			"items": [
				{
					"type": "doctype",
					"name": "Shift Details",
					"description": _("Shift Definition Details"),
				},
			]
		},
		{
			"label": _("Setup"),
			"icon": "icon-gear",
			"items": [
				{
					"type": "doctype",
					"name": "Roster",
					"description": _("Define which employees are in which Shift during a period"),
				},
			]
		}
	]