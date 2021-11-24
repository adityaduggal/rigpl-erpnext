from frappe import _

def get_data():
    return [
            {
                    "label": _("RIGPL Reports"),
                    "items": [
                            {
                                    "type": "report",
                                    "is_query_report": True,
                                    "name": "Calculate ROL",
                                    "doctype": "Stock Ledger Entry",
                            },
                            {
                                    "type": "report",
                                    "is_query_report": True,
                                    "name": "Item Report RIGPL",
                                    "doctype": "Item",
                            },
                            {
                                    "type": "report",
                                    "is_query_report": True,
                                    "name": "Stock Valuation",
                                    "doctype": "Stock Entry Detail",
                            },
                            {
                                    "type": "report",
                                    "is_query_report": True,
                                    "name": "Value Addition",
                                    "doctype": "Tool Type",
                            },
                            {
                                "type": "report",
                                "is_query_report": True,
                                "name": "Valuation Rate",
                                "doctype": "Purchase Invoice",
                            },
                            {
                                "type": "report",
                                "is_query_report": True,
                                "name": "Stock Ledger with Valuation",
                                "doctype": "Integration Request",
                            },
                            {
                                "type": "report",
                                "is_query_report": True,
                                "name": "Item Lead Times",
                                "doctype": "Stock Ledger Entry",
                            },
                            {
                                "type": "report",
                                "is_query_report": True,
                                "name": "Stock Ageing RIGPL",
                                "doctype": "Stock Ledger Entry",
                            },
                    ]
            }
    ]
