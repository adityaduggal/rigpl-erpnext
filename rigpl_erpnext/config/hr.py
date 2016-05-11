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
		},
		{
			"label": _("Rohit Reports"),
			"icon": "icon-paper-clip",
			"items": [
				{
					"type": "report",
					"is_query_report": True,
					"name": "Attendance Performance Analysis",
					"doctype": "Attendance",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Employee Loan Analysis",
					"doctype": "Employee Loan",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Roster",
					"doctype": "Roster",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Leave Application Report",
					"doctype": "Leave Application",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "List of Holidays",
					"doctype": "Holiday List",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Salary Structure",
					"doctype": "Salary Structure",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Employee Attendance",
					"doctype": "Attendance",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Monthly Attendance Time Based",
					"doctype": "Attendance",
				},
			]
		}
	]