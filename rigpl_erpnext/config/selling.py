from frappe import _


def get_data():
    return [
        {
            "label": _("Sales"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Trial Tracking",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Customers with SO",
                    "doctype": "Campaign",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Pending Orders",
                    "doctype": "Sales Order",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Trial Tracking",
                    "label": "Trial Tracking Report",
                    "doctype": "Sales Order",
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
                    "name": "Address Book RIGPL",
                    "label": "Address Book",
                    "doctype": "Customer",
                },
            ]
        },
        {

            "label": _("Items and Pricing"),
            "items": [
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Compare Pricing",
                    "doctype": "Price List",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "RIGPL Price List",
                    "doctype": "Item Price",
                },
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Stock Status",
                    "doctype": "Item",
                },
            ]
        }
    ]
