# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document

from rigpl_erpnext.website_rigpl.seo import meta
from rigpl_erpnext.website_rigpl.website_data.seo.importer import create_missing_records


class SEOSettings(Document):
    def validate(self):
        meta.check_templates(self, ("site_name", "title_template", "description_template"))

    def on_update(self):
        meta.clear_caches()


@frappe.whitelist()
def create_records() -> list:
    """Creates the default Schema Templates and SEO Rules that do not exist."""
    if not frappe.has_permission("SEO Settings", "write"):
        frappe.throw("No permission to write SEO Settings", frappe.PermissionError)
    return create_missing_records()
