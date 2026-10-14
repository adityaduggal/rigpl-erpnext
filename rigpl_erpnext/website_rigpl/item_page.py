"""
Website context changes for standard pages, called by the `update_website_context` hook.
Add a handler to PAGE_HANDLERS for each doctype page that RIGPL changes (issue #98).
"""
from __future__ import annotations

ITEM_TEMPLATE_PAGE = "rigpl_erpnext/templates/generators/rigpl_item_template.html"


def update_website_context(context) -> dict | None:
    doc = context.get("doc")
    handler = PAGE_HANDLERS.get(getattr(doc, "doctype", None))
    return handler(doc) if handler else None


def website_item_context(doc) -> dict | None:
    """A template Website Item shows its variant table instead of ERPNext's variant picker (#95)."""
    if not doc.get("has_variants"):
        return None
    return {"template": ITEM_TEMPLATE_PAGE}


PAGE_HANDLERS = {"Website Item": website_item_context}
