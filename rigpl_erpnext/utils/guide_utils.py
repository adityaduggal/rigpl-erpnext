"""User guides in `docs/user/`, shown in a desk dialog (#186). They are not web pages."""
from __future__ import unicode_literals

import re

import frappe
from frappe.utils import escape_html, md_to_html

# {guide: DocType that the user must be able to read}
GUIDES = {
    "bom_templates": "BOM Template RIGPL",
    "process_sheet": "Process Sheet",
    "rigpl_settings": "RIGPL Settings",
    "sales_order_quantity": "Sales Order",
    "website_seo_schema": "Schema Template",
}
# Guides that show each `##` section collapsed
COLLAPSED_GUIDES = ("rigpl_settings", "sales_order_quantity")


@frappe.whitelist()
def get_user_guide(guide):
    """Returns the guide as HTML for a user who can read its DocType."""
    doctype = GUIDES.get(guide)
    if not doctype:
        frappe.throw("Unknown guide: {}".format(guide))
    if not frappe.has_permission(doctype, "read"):
        frappe.throw("Not permitted to read this guide", frappe.PermissionError)
    with open(frappe.get_app_path("rigpl_erpnext", "docs", "user", guide + ".md")) as guide_file:
        text = guide_file.read()
    if guide in COLLAPSED_GUIDES:
        return get_collapsed_html(text)
    return md_to_html(text)


def get_collapsed_html(text):
    intro, *sections = re.split(r"^## ", text, flags=re.MULTILINE)
    html = [md_to_html(intro)]
    for section in sections:
        title, body = section.split("\n", 1)
        html.append("<details><summary><b>{0}</b></summary>{1}</details>".format(
            escape_html(title), md_to_html(body)))
    return "".join(html)
