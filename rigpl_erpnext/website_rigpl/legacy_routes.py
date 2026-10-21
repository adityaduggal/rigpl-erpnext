"""
Send an old website URL that has no page now to its current page, with one 301 (#84).

`Item.route` still holds the rigpl.com (v12) route of each item. Frappe shows the 404 page when
no page and no Website Route Redirect matches a path. `www/404.py` then asks
`get_legacy_target` for the page to send the visitor to. The lookup runs only for a missing
page, so other pages do not pay for it. It reads the routes of today, so a later route change
does not make a redirect chain.
"""
from __future__ import annotations

from typing import Dict, Optional

import frappe

from rigpl_erpnext.website_rigpl.routes import parent_path


def pick_item_target(
    item_code: str, template_code: Optional[str], published_routes: Dict[str, str], group_route: Optional[str]
) -> Optional[str]:
    """The most specific live page for an item: its Website Item, then its template, then its group."""
    return published_routes.get(item_code) or published_routes.get(template_code or "") or group_route or None


def get_legacy_target(path: str) -> Optional[str]:
    """The route to redirect `path` to, or None for a real 404."""
    if not isinstance(path, str):
        return None
    path = path.strip("/ ")
    if not path:
        return None
    target = item_target(path) or unpublished_variant_target(path) or hidden_group_target(path)
    return target if target != path else None


def item_target(path: str) -> Optional[str]:
    """The current page of the Item whose v12 route is `path`."""
    items = frappe.get_all(
        "Item",
        filters={"route": path},
        fields=["name", "variant_of", "item_group"],
        order_by="has_variants desc",
        limit=1,
    )
    if not items:
        return None
    item = items[0]
    codes = [code for code in (item.name, item.variant_of) if code]
    published = dict(
        frappe.get_all(
            "Website Item",
            filters={"item_code": ("in", codes), "published": 1},
            fields=["item_code", "route"],
            as_list=True,
        )
    )
    return pick_item_target(item.name, item.variant_of, published, shown_group_route(item.item_group))


def unpublished_variant_target(path: str) -> Optional[str]:
    """`<template route>/<item code>` of a variant that is not published now: its template page."""
    parent = parent_path(path)
    if parent and frappe.db.exists("Website Item", {"route": parent, "published": 1, "has_variants": 1}):
        return parent
    return None


def hidden_group_target(path: str) -> Optional[str]:
    """The route of an Item Group that is not shown in the website: its nearest shown ancestor."""
    group = frappe.db.get_value("Item Group", {"route": path}, "name")
    return shown_group_route(group) if group else None


def shown_group_route(group: Optional[str]) -> Optional[str]:
    """The route of `group` if it shows in the website, else of its nearest ancestor that shows."""
    if not group:
        return None
    lft, rgt = frappe.db.get_value("Item Group", group, ["lft", "rgt"]) or (None, None)
    if lft is None:
        return None
    routes = frappe.get_all(
        "Item Group",
        filters={"lft": ("<=", lft), "rgt": (">=", rgt), "show_in_website": 1, "route": ("is", "set")},
        order_by="lft desc",
        limit=1,
        pluck="route",
    )
    return routes[0] if routes else None
