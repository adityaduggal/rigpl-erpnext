# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
from frappe.model.document import Document

from rigpl_erpnext.website_rigpl.seo import meta


class SEOSettings(Document):
    def validate(self):
        meta.check_templates(self, ("title_template", "description_template"))

    def on_update(self):
        meta.clear_caches()
