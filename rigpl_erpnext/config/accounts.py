from frappe import _

def get_data():
    return [
            {
                    "label": _("Accounts Receivable"),
                    "items": [
                            {
                                    "type": "doctype",
                                    "name": "Carrier Tracking",
                            },
                        {
                                "type": "report",
                                "is_query_report": True,
                                "name": "DN To Be Billed",
                                "doctype": "Sales Invoice",
                            },
                    ]
            },
        {
                "label": _("Financial Statements"),
                "items": [
                    {
                        "type": "report",
                        "is_query_report": True,
                        "name": "Cost Wise PandL RIGPL",
                        "label": "Cost Center Wise Profit and Loss Statement",
                        "doctype": "Cost Center",
                    },
                ]
            },
        {
                "label": _("Accounts Payable"),
                "items": [
                    {
                        "type": "doctype",
                        "name": "Turn Over Discount",
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
                    },
                ]
            },
        {
                "label": _("Accounting Masters"),
                "items": [
                    {
                        "type": "doctype",
                        "name": "Shipment Package",
                    },
                ]
            },
        {
                "label": _("Settings"),
                "items": [
                    {
                        "type": "doctype",
                        "name": "Shipway Settings",
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
                        {
                                "type": "report",
                                "is_query_report": True,
                                "name": "BRC Tracking",
                                "label": "BRC Tracking Report",
                                "doctype": "BRC MEIS Tracking",
                            },
                    ]
        },
    ]
