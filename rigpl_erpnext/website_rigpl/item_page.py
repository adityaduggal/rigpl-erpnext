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
    return handler(context) if handler else None


def website_item_context(context) -> dict | None:
    """A template Website Item shows its variant table instead of ERPNext's variant picker (#95).
    Any other Website Item keeps ERPNext's page, with the stock capped (#127).
    """
    if context.doc.get("has_variants"):
        return {"template": ITEM_TEMPLATE_PAGE}

    shopping_cart = context.get("shopping_cart")
    if not shopping_cart or not shopping_cart.get("product_info"):
        return None
    product_info = cap_product_info(shopping_cart["product_info"])
    return {"shopping_cart": frappe._dict(shopping_cart, product_info=product_info)}


PAGE_HANDLERS = {"Website Item": website_item_context}
