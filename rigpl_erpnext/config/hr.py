from frappe import _

def get_data():
	return [
		{
			"label": _("Loans"),
			"items": [
				{
					"type": "doctype",
					"name": "Employee Advance",
					"description": _("Employee Advance"),
				},
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Employee Balances RIGPL",
                    "doctype": "Salary Slip",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Employee Loan Analysis",
                    "doctype": "Employee Advance",
                },
			]
		},
        {
            "label": _("Attendance"),
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
        },
        {
            "label": _("Payroll"),
            "items":[
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Salary Structure",
                    "label": "Salary Structure Report RIGPL",
                    "doctype": "Salary Structure",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Salary Register",
                    "label": "Salary Register Report RIGPL",
                    "doctype": "Salary Slip",
                },
            ]
        },
		{
			"label": _("Leaves"),
			"items": [
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
                    "label": "List of Holidays Report",
					"doctype": "Holiday List",
				},
			]
		}
	]
