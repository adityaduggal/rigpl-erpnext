from frappe import _

def get_data():
    return [
        {
            "label": _("Settings"),
            "items": [
                {
                    "type": "doctype",
                    "name": "RIGPL Settings",
                },
                {
                    "type": "doctype",
                    "name": "User Permission Settings",
                    "label": "User Permission Setttings for RIGPL"
                },
                {
                    "type": "doctype",
                    "name": "User Share Settings",
                    "label": "User Share Settings for RIGPL"
                },
            ]
        }
    ]