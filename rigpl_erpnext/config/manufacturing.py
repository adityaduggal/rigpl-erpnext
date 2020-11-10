from frappe import _


def get_data():
    return [
        {
            "label": _("Bill of Materials"),
            "items": [
                {
                    "type": "doctype",
                    "name": "BOM Template RIGPL",
                    "label": "BOM Template",
                },
                {
                    "type": "doctype",
                    "name": "Made to Order Item Attributes",
                    "label": "Made to Order Item Definitions",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "BOM Templates",
                    "label": "BOM Templates Report",
                    "doctype": "BOM Template RIGPL",
                },
            ]
        },
        {
            "label": _("Tools"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Create Bulk Process Sheet",
                },
            ]
        },
        {
            "label": _("Production"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Important Documents",
                },
                {
                    "type": "doctype",
                    "name": "Process Sheet",
                },
                {
                    "type": "doctype",
                    "name": "Process Job Card RIGPL",
                    "label": "Job Card RIGPL"
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Process Sheet Analysis",
                    "doctype": "Process Sheet",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Production and Planning Report RIGPL",
                    "label": "Production Planning",
                    "doctype": "Process Job Card RIGPL",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "MTO Stock Ledger",
                    "label": "Made to Order Stock Ledger",
                    "doctype": "Process Job Card RIGPL",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Standards and Drawings RIGPL",
                    "label": "Standards and Drawings Report",
                    "doctype": "Important Documents",
                },
            ]
        },
        {
            "label": _("Reports"),
            "items": [
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Items For Production",
                    "doctype": "Work Order",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Pending So (Prd)",
                    "doctype": "Work Order",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Standards and Drawings RIGPL",
                    "doctype": "Important Documents",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Label Printing Database RIGPL",
                    "doctype": "Item",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Items without BOM Templates",
                    "doctype": "BOM Template RIGPL",
                },
            ]
        }

    ]
