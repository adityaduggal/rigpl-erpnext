from frappe import _


def get_data():
    return [
        {
            "label": _("Settings"),
            "items": [
                {
                    "type": "doctype",
                    "name": "RIGPL Settings",
                    "label": _("RIGPL Settings"),
                    "description": _("Settings for RIGPL App"),
                },
            ]
        },
        {
            "label": _("Settings"),
            "items": [
                {
                    "type": "doctype",
                    "name": "User Permission Settings",
                    "label": _("RIGPL Auto User Permission Settings"),
                    "description": _("Settings for Auto User Permissions"),
                },
            ]
        },
        {
            "label": _("Settings"),
            "items": [
                {
                    "type": "doctype",
                    "name": "User Share Settings",
                    "label": _("RIGPL User Share Settings"),
                    "description": _("Automatically Shares Docs with Users based on Rules"),
                },
            ]
        },
    ]