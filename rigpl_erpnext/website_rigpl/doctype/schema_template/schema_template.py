# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
from __future__ import annotations

from typing import List, Optional, Tuple

import frappe
from frappe.model.document import Document
from frappe.utils import escape_html
from frappe.website.render import clear_cache
from jinja2 import TemplateSyntaxError

from rigpl_erpnext.website_rigpl.item_page import find_page_rule
from rigpl_erpnext.website_rigpl.seo import builder, context, meta, required
from rigpl_erpnext.website_rigpl.seo.sandbox import check_syntax

LINK_TYPES = ("Template", "Template List")


class SchemaTemplate(Document):
    def validate(self):
        self.clean_properties()
        self.check_expressions()
        if self.enabled:
            self.check_type_properties()
            if not self.flags.skip_route_check:
                self.check_sample_route()

    def on_update(self):
        self.clear_caches()

    def on_trash(self):
        self.clear_caches()

    def after_rename(self, old_name, new_name, merge=False):
        self.clear_caches()

    def render_route(self, route: str) -> Tuple[Optional[dict], List[builder.BuildError], bool]:
        """The graph of this document, saved or not, for a route. The last value is False when
        `iterate_over` or `condition` gave no node to build."""
        web_context = context.get_route_context(route)
        errors = []
        rule = find_page_rule(web_context)
        shown_title = meta.build_meta(web_context, rule, errors).get("title")
        variables = context.build_variables(web_context, shown_title)
        is_block = self.applies_to == builder.BLOCK_TEMPLATES
        blocks = context.get_blocks(web_context.get("doc")) if is_block else []
        graph_builder = builder.GraphBuilder(errors)
        nodes = builder.merge_by_id(graph_builder.page_nodes(self, variables, blocks))
        return builder.make_graph(nodes), errors, self.name in graph_builder.reached

    def clean_properties(self):
        self.schema_type = (self.schema_type or "").strip()
        for row in self.properties:
            row.property = (row.property or "").strip()
            if row.property.startswith("@"):
                frappe.throw(
                    "Row {}: do not add {}. Use Schema Type and ID Expression.".format(
                        row.idx, escape_html(row.property)
                    )
                )
            if row.value_type in LINK_TYPES and not row.linked_template:
                frappe.throw("Row {}: set the Linked Template".format(row.idx))

    def check_expressions(self):
        sources = [
            (self.meta.get_label(field), self.get(field))
            for field in ("id_expression", "condition", "iterate_over")
        ]
        for row in self.properties:
            sources.append(("Row {} Condition".format(row.idx), row.condition))
            if row.value_type == "Expression":
                sources.append(("Row {} Value".format(row.idx), row.value))

        for label, source in sources:
            try:
                check_syntax(source)
            except TemplateSyntaxError as e:
                frappe.throw("{}: {}".format(label, escape_html(str(e))))

    def check_type_properties(self):
        groups = required.required_groups(self.schema_type, self.merchant_listing)
        missing = required.missing(groups, [row.property for row in self.properties])
        if missing:
            frappe.throw(
                "{} needs these properties: {}".format(escape_html(self.schema_type), ", ".join(missing))
            )

    def check_sample_route(self):
        graph, errors, reached = self.render_route(self.sample_route)
        if reached:
            self.check_required_values(graph, errors)
        else:
            frappe.msgprint(
                "The template makes no node for the sample route, so the required values are not checked.",
                indicator="orange",
            )
        if errors:
            frappe.msgprint(
                "<br>".join(escape_html(describe(error)) for error in errors),
                title="Expression errors on the sample route",
                indicator="orange",
            )

    def check_required_values(self, graph: Optional[dict], errors: List[builder.BuildError]):
        nodes = graph["@graph"] if graph else []
        present = {key for node in nodes for key in node}
        failed = []
        for row in self.properties:
            if row.required and row.property not in present:
                reasons = [
                    e.message for e in errors if (e.template, e.property) == (self.name, row.property)
                ]
                failed.append(" ".join(["Row {}: {} has no value.".format(row.idx, row.property)] + reasons))
        if failed:
            frappe.throw("<br>".join(escape_html(line) for line in failed))

    def clear_caches(self):
        builder.clear_template_cache()
        clear_cache()


@frappe.whitelist()
def preview(name: str, route: str = None) -> dict:
    """The JSON-LD of a saved Schema Template for a route."""
    # `throw=True` of v13 raises ValidationError, not PermissionError
    if not frappe.has_permission("Schema Template", "write"):
        frappe.throw("No permission to write Schema Template", frappe.PermissionError)
    graph, errors, _ = frappe.get_doc("Schema Template", name).render_route(route)
    return {
        "json": builder.to_json(graph, indent=2) if graph else "",
        "errors": [dict(error._asdict()) for error in errors],
    }


def describe(error: builder.BuildError) -> str:
    return "{} / {}: {}".format(error.template, error.property, error.message)
