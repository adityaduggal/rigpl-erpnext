# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import escape_html
from jinja2 import TemplateError

from rigpl_erpnext.website_rigpl.seo import context, meta
from rigpl_erpnext.website_rigpl.seo.sandbox import plain_text, render_text

LIMITED_FIELDS = ("title", "description")


class SEORule(Document):
    def validate(self):
        self.check_match()
        meta.check_templates(self, ["{}_template".format(field) for field in meta.TEMPLATE_FIELDS])
        self.check_schema_templates()
        if self.enabled:
            self.warn_lengths()

    def on_update(self):
        meta.clear_caches()

    def on_trash(self):
        meta.clear_caches()

    def after_rename(self, old_name, new_name, merge=False):
        meta.clear_caches()

    def check_match(self):
        self.route_pattern = (self.route_pattern or "").strip().lstrip("/")
        if not self.reference_doctype and not self.route_pattern:
            frappe.throw("Set the Reference DocType or the Route Pattern", frappe.ValidationError)

    def check_schema_templates(self):
        names = [row.schema_template for row in self.schema_templates]
        if not names:
            return
        filters = {"name": ["in", names], "applies_to": ["!=", "Page Type"]}
        wrong = frappe.get_all("Schema Template", filters=filters, pluck="name")
        if wrong:
            frappe.throw(
                "Applies To must be Page Type: {}".format(escape_html(", ".join(wrong))),
                frappe.ValidationError,
            )

    def warn_lengths(self):
        """A warning only. With no sample route, only plain text can be checked."""
        sources = {field: self.get(field + "_template") or "" for field in LIMITED_FIELDS}
        if self.sample_route:
            variables = context.build_variables(context.get_route_context(self.sample_route))
        else:
            variables = {}
            sources = {field: source for field, source in sources.items() if "{" not in source}

        warnings = []
        for field, source in sources.items():
            try:
                text = plain_text(render_text(source, variables))
            except (TemplateError, TypeError, ValueError, ArithmeticError, LookupError) as e:
                warnings.append("{}: {}".format(field.title(), e))
                continue
            limit = meta.get_limit(field)
            if len(text) > limit:
                warnings.append(
                    "{}: {} characters. The limit is {}.".format(field.title(), len(text), limit)
                )
        if warnings:
            frappe.msgprint(
                "<br>".join(escape_html(line) for line in warnings), title="SEO Rule", indicator="orange"
            )
