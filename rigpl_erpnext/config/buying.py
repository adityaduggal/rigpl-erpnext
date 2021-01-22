from frappe import _


def get_data():
    return [
        {
            "label": _("Purchasing"),
            "items": [
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Pending Purchase Orders",
                    "doctype": "Purchase Order",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Sub-Contracting Mismatch",
                    "doctype": "Purchase Order",
                },
            ]
        },
    ]
