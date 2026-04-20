#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

import frappe


def before_insert(doc, method):
    """Set ignore_permlevel_for_fields flag before validate_higher_perm_levels runs.

    During insert, the flow is: before_insert → validate_higher_perm_levels → validate.
    The employment_type field (permlevel=1, mandatory) gets auto-filled from User Permission,
    but validate_higher_perm_levels strips it for users without write access at permlevel 1.
    This flag tells Frappe to skip the permlevel check for this specific field.
    """
    doc.flags.ignore_permlevel_for_fields = doc.flags.get(
        "ignore_permlevel_for_fields", []
    )
    if "employment_type" not in doc.flags.ignore_permlevel_for_fields:
        doc.flags.ignore_permlevel_for_fields.append("employment_type")


def validate(doc, method):
    set_employment_type_from_user_permission(doc)


def set_employment_type_from_user_permission(doc):
    """Auto-fill employment_type from User Permission if it's empty.

    This acts as a safety net: if the employment_type field was stripped by
    validate_higher_perm_levels (e.g. during save/update), or if it was not
    sent by the client, this re-fills it from the user's User Permission.
    """
    if not doc.employment_type:
        user_perms = frappe.permissions.get_user_permissions(frappe.session.user)
        et_perms = user_perms.get("Employment Type", [])
        if et_perms:
            doc.employment_type = et_perms[0].get("doc")
