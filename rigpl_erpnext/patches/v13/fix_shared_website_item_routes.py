import re

import frappe
from frappe.website.render import clear_cache

from rigpl_erpnext.website_rigpl.routes import plan_shared_route_fixes


def execute():
    """
    Give each Website Item a route of its own (#99). After the v13 migration, 2,493 Website
    Items shared 133 routes, so 20 template pages showed a variant. Idempotent: when no
    route is shared, the plan is empty and nothing changes.
    """
    web_items = frappe.get_all(
        "Website Item", fields=["name", "item_code", "route", "has_variants", "variant_of"]
    )
    templates = [row.item_code for row in web_items if row.has_variants]
    item_routes = dict(
        frappe.get_all("Item", filters={"name": ("in", templates)}, fields=["name", "route"], as_list=True)
    ) if templates else {}

    new_routes, redirects = plan_shared_route_fixes(web_items, item_routes)

    for name, route in new_routes.items():
        frappe.db.set_value("Website Item", name, "route", route, update_modified=False)

    added = add_redirects(redirects)
    clear_cache()
    print(f"Website Item routes changed: {len(new_routes)}. Route redirects added: {added}.")


def add_redirects(redirects):
    """Website Route Redirect sources are regular expressions, so each route is escaped.

    Rows go in directly: saving Website Settings would also run its unrelated validations.
    """
    existing = set(frappe.get_all("Website Route Redirect", pluck="source"))
    idx = len(existing)
    added = 0
    for route, target in redirects:
        source = re.escape(route)
        if source in existing:
            continue
        idx += 1
        frappe.get_doc(
            {
                "doctype": "Website Route Redirect",
                "parent": "Website Settings",
                "parenttype": "Website Settings",
                "parentfield": "route_redirects",
                "idx": idx,
                "source": source,
                "target": "/" + target,
            }
        ).db_insert()
        existing.add(source)
        added += 1
    return added
