"""User guides in `docs/user/`, shown in a desk dialog (#186). They are not web pages."""
from __future__ import unicode_literals

import frappe
from frappe.utils import md_to_html

# {guide: DocType that the user must be able to read}
GUIDES = {
    "bom_templates": "BOM Template RIGPL",
    "process_sheet": "Process Sheet",
}


@frappe.whitelist()
def get_user_guide(guide):
    """Returns the guide as HTML for a user who can read its DocType."""
    doctype = GUIDES.get(guide)
    if not doctype:
        frappe.throw("Unknown guide: {}".format(guide))
    if not frappe.has_permission(doctype, "read"):
        frappe.throw("Not permitted to read this guide", frappe.PermissionError)
    with open(frappe.get_app_path("rigpl_erpnext", "docs", "user", guide + ".md")) as guide_file:
        return md_to_html(guide_file.read())
