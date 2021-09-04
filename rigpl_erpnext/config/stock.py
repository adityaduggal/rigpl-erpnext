from frappe import _

def get_data():
    return [
            {
                    "label": _("Stock Reports"),
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
                    ]
            }
    ]
