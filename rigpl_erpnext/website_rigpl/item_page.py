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
    # the graph reads the page before the meta tags, so that `page.h1` keeps the document title
    page = dict(context, **values)
    add_meta_tags(context, values)
    # the visible breadcrumb ends with the title that the meta tags can change
    add_schema_graph(context, values, page)
    return values or None


def add_schema_graph(context, values: dict, page: dict = None) -> None:
    """Adds the JSON-LD of the page's Schema Templates to `values["head_include"]` (#260).
    A failure is logged and leaves the page as it was."""
    try:
        write_schema_graph(context, values, page)
    except Exception:
        log_seo_failure(context)


def add_meta_tags(context, values: dict) -> None:
    """Writes the title, canonical and meta tags of SEO Settings and SEO Rules (#261).
    A failure is logged and leaves the page as it was."""
    try:
        write_meta_tags(context, values)
    except Exception:
        log_seo_failure(context)


def write_meta_tags(context, values: dict) -> None:
    from rigpl_erpnext.website_rigpl.seo.builder import log_errors
    from rigpl_erpnext.website_rigpl.seo.context import PREVIEW_FLAG, get_route
    from rigpl_erpnext.website_rigpl.seo.meta import build_meta

    if frappe.flags.get(PREVIEW_FLAG):
        return
    web_context = frappe._dict(dict(context, **values))
    errors = []
    changes = build_meta(web_context, find_page_rule(web_context), errors)
    log_errors(errors, get_route(web_context))
    values.update(changes)


def find_page_rule(context):
    from rigpl_erpnext.website_rigpl.seo.context import get_route
    from rigpl_erpnext.website_rigpl.seo.meta import find_rule

    doc = context.get("doc")
    return find_rule(getattr(doc, "doctype", None), get_route(context))


def get_page_template_names(context) -> list:
    """The enabled Page Type templates of the SEO Rule of the page. A failure is logged and
    leaves the Site templates."""
    try:
        from rigpl_erpnext.website_rigpl.seo.builder import get_template_names

        rule = find_page_rule(context)
        wanted = {row.schema_template for row in rule.schema_templates} if rule else set()
        return [name for name in get_template_names("Page Type") if name in wanted] if wanted else []
    except Exception:
        log_seo_failure(context)
        return []


def write_schema_graph(context, values: dict, page: dict = None) -> None:
    """`page` is the page before the meta tags. `values` can hold the title that the page shows."""
    # imported here, so that an error in the engine cannot stop every website page
    from rigpl_erpnext.website_rigpl.seo.builder import (
        BLOCK_TEMPLATES,
        DOCTYPE,
        PAGE_PARTS,
        build_graph,
        get_template_names,
        log_errors,
        to_script,
    )
    from rigpl_erpnext.website_rigpl.seo.context import PREVIEW_FLAG, build_variables, get_route

    if frappe.flags.get(PREVIEW_FLAG):
        return
    block_names = get_template_names(BLOCK_TEMPLATES)
    part_names = [name for part in PAGE_PARTS for name in get_template_names(part)]
    names = get_template_names("Site") + part_names + get_page_template_names(context) + block_names
    if not names:
        return
    templates = [frappe.get_cached_doc(DOCTYPE, name) for name in names]
    errors = []
    blocks = get_page_blocks(context) if block_names else []
    variables = build_variables(page or dict(context, **values), values.get("title"))
    graph = build_graph(templates, variables, errors, blocks)
    log_errors(errors, get_route(context))
    if graph:
        head_include = values.get("head_include", context.get("head_include")) or ""
        values["head_include"] = head_include + to_script(graph)


def get_page_blocks(context) -> list:
    """A failure is logged and leaves the graph without block markup."""
    try:
        from rigpl_erpnext.website_rigpl.seo.context import get_blocks

        return get_blocks(context.get("doc"))
    except Exception:
        log_seo_failure(context)
        return []


def log_seo_failure(context) -> None:
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
