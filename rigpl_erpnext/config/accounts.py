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
					"name": "DN To Be Billed",
					"doctype": "Sales Invoice",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "PR to be Billed",
					"doctype": "Purchase Invoice",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "CForms Analysis",
					"doctype": "C-Form",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Sales Partner Commission Details",
					"doctype": "Sales Invoice",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "TOD Sales Invoice",
					"doctype": "Sales Invoice",
				}
			]
		}
	]
