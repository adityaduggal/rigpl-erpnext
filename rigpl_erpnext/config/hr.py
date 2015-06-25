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
		}
	]