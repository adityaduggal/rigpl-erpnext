"""
Website context changes for standard pages, called by the `update_website_context` hook.
Add a handler to PAGE_HANDLERS for each doctype page that RIGPL changes (issue #98).
"""
from __future__ import annotations

import frappe

from rigpl_erpnext.website_rigpl.catalog import cap_product_info

ITEM_TEMPLATE_PAGE = "rigpl_erpnext/templates/generators/rigpl_item_template.html"


def update_website_context(context) -> dict | None:
    doc = context.get("doc")
    handler = PAGE_HANDLERS.get(getattr(doc, "doctype", None))
    values = dict((handler(context) if handler else None) or {})
    add_schema_graph(context, values)
    return values or None


def add_schema_graph(context, values: dict) -> None:
    """Adds the JSON-LD of the Site Schema Templates to `values["head_include"]` (#260).
    A failure is logged and leaves the page as it was."""
    try:
        write_schema_graph(context, values)
    except Exception:
        log_schema_failure(context)


def write_schema_graph(context, values: dict) -> None:
    # imported here, so that an error in the engine cannot stop every website page
    from rigpl_erpnext.website_rigpl.seo.builder import (
        DOCTYPE,
        build_graph,
        get_template_names,
        log_errors,
        to_script,
    )
    from rigpl_erpnext.website_rigpl.seo.context import PREVIEW_FLAG, build_variables, get_route

    if frappe.flags.get(PREVIEW_FLAG):
        return
    names = get_template_names("Site")
    if not names:
        return
    templates = [frappe.get_cached_doc(DOCTYPE, name) for name in names]
    errors = []
    graph = build_graph(templates, build_variables(dict(context, **values)), errors)
    log_errors(errors, get_route(context))
    if graph:
        head_include = values.get("head_include", context.get("head_include")) or ""
        values["head_include"] = head_include + to_script(graph)


def log_schema_failure(context) -> None:
    traceback = frappe.get_traceback()
    try:
        from rigpl_erpnext.website_rigpl.seo.builder import BuildError, log_errors
        from rigpl_erpnext.website_rigpl.seo.context import get_route

        log_errors([BuildError("", "", traceback)], get_route(context))
    except Exception:
        # the page must show, also when the Error Log cannot be written
        frappe.logger().error(traceback)


def website_item_context(context) -> dict | None:
    """A template Website Item shows its variant table instead of ERPNext's variant picker (#95).
    Any other Website Item keeps ERPNext's page, with the stock capped (#127). A variant's
    breadcrumb ends with its template (#104).
    """
    if context.doc.get("has_variants"):
        return {"template": ITEM_TEMPLATE_PAGE}

    values = {}
    shopping_cart = context.get("shopping_cart")
    if shopping_cart and shopping_cart.get("product_info"):
        product_info = cap_product_info(shopping_cart["product_info"])
        values["shopping_cart"] = frappe._dict(shopping_cart, product_info=product_info)
    if context.doc.get("variant_of"):
        parents = add_template_breadcrumb(context.get("parents") or [], context.doc.variant_of)
        if parents:
            values["parents"] = parents
    return values or None


def add_template_breadcrumb(parents: list, template: str) -> list | None:
    """ERPNext's breadcrumb (Home, the shown categories) plus the published template Website
    Item, as a new list. None if the template has no published Website Item."""
    web_item = frappe.db.get_value(
        "Website Item", {"item_code": template, "published": 1}, ["web_item_name", "route"], as_dict=True
    )
    if not web_item or not web_item.route:
        return None
    return list(parents) + [{"name": web_item.web_item_name or template, "route": web_item.route}]


PAGE_HANDLERS = {"Website Item": website_item_context}
