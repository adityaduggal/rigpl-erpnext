from frappe import _

def get_data():
	return [
		{
			"label": _("Accounts Receivable"),
			"items": [
				{
					"type": "doctype",
					"name": "Carrier Tracking",
					"description": _("Track Shipments sent via Courier"),
				},
			]
		},
		{
			"label": _("Banking and Payments"),
			"icon": "icon-star",
			"items": [
				{
					"type": "doctype",
					"name": "BRC MEIS Tracking",
					"description": _("Track BRC and MEIS Status"),
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
					"name": "Asset Analysis",
					"doctype": "Asset Category",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "BRC Tracking",
					"doctype": "BRC MEIS Tracking",
				},
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
