from frappe import _

def get_data():
	return [
		{
			"label": _("Documents"),
			"icon": "icon-star",
			"items": [
				{
					"type": "doctype",
					"name": "Trial Tracking",
					"description": _("Trial database."),
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
					"name": "Customers with SO",
					"doctype": "Campaign",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Follow Up",
					"doctype": "Customer",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Sales Partner SO Analysis",
					"doctype": "Sales Order",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Trial Tracking",
					"doctype": "Sales Order",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Price List",
					"doctype": "Item Price",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Pending Orders",
					"doctype": "Sales Order",
				},
			]
		}
	]
