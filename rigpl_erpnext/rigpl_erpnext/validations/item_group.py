# -*- coding: utf-8 -*-
"""
Item Group route (#97). A web group (shown in the website, or with a Website Item) gets its
route from `routes.build_group_route`: the Website Slug of each ancestor with Include in URL,
then its own Website Slug. ERPNext sets a route only when it is empty, and this hook runs
after ERPNext validate, so it sets the route on each save.

The routes of descendant groups and of Website Items are not changed here. `on_update`
enqueues `route_sync.rebuild_routes`, which changes them in one background job.
"""
from __future__ import annotations

import frappe
from frappe import _

from rigpl_erpnext.website_rigpl.route_sync import (
    Redirect,
    apply_redirects,
    checks_off,
    enqueue_rebuild,
    get_route_limits,
    throw_if_route_taken,
    throw_route_errors,
)
from rigpl_erpnext.website_rigpl.routes import build_group_route, check_group_budget, validate_route

# A change to one of these fields can change the route of this group or of its descendants.
ROUTE_FIELDS = (
    "website_slug",
    "include_in_url",
    "item_group_name",
    "parent_item_group",
    "show_in_website",
    "route",
)


def validate(doc, method):
    if checks_off() or not doc.parent_item_group or not is_web_group(doc):
        return

    max_length, max_depth = get_route_limits()
    try:
        route = build_group_route(get_ancestors(doc.parent_item_group) + [doc.as_dict()], max_depth)
    except ValueError as e:
        frappe.throw(str(e), title=_("Item Group Route Too Deep"))

    throw_route_errors("Item Group", route, validate_route(route, max_length) + check_group_budget(route, max_length))
    throw_if_route_taken("Item Group", doc.name, route)
    doc.route = route


def on_update(doc, method):
    before = doc.get_doc_before_save()
    if not before:
        return
    if before.route and before.route != doc.route and is_web_group(doc):
        apply_redirects([Redirect(before.route, doc.route, False)], {before.route: doc.route}, [doc.route])
    if any(doc.has_value_changed(field) for field in ROUTE_FIELDS):
        enqueue_rebuild()


def is_web_group(doc) -> bool:
    return bool(doc.show_in_website) or bool(frappe.db.exists("Website Item", {"item_group": doc.name}))


def get_ancestors(parent: str) -> list:
    """`parent` and its ancestors, without the root, from the top down. One query."""
    bounds = frappe.db.get_value("Item Group", parent, ["lft", "rgt"], as_dict=True)
    if not bounds:
        return []
    return frappe.get_all(
        "Item Group",
        filters={"lft": ("<=", bounds.lft), "rgt": (">=", bounds.rgt), "parent_item_group": ("is", "set")},
        fields=["name", "item_group_name", "website_slug", "include_in_url"],
        order_by="lft",
    )
