"""
Apply the route rules of `routes.py` to the database (#97, #102).

- Website Item and Web Page `validate` check the route. Website Item also makes it.
- A changed route gets a Website Route Redirect (301) from the old route.
- A change to an Item Group or to a template Website Item enqueues `rebuild_routes`, which
  makes the routes of all web groups and Website Items again. One job runs at a time.

During a patch the checks do not run: the ERPNext v13 migration makes Website Items before
the patch `rebuild_website_routes` makes the new routes.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.background_jobs import enqueue, get_jobs
from frappe.website.render import clear_cache

from rigpl_erpnext.website_rigpl.routes import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_LENGTH,
    Redirect,
    build_item_route,
    hijacking_redirects,
    plan_route_rebuild,
    retarget_redirects,
    validate_route,
)

REBUILD_JOB = "rigpl_rebuild_routes"


def get_route_limits() -> Tuple[int, int]:
    """(max route length, max category segments) from RIGPL Settings. Empty uses the default."""
    settings = frappe.get_cached_doc("RIGPL Settings")
    return (
        cint(settings.get("website_route_max_length")) or DEFAULT_MAX_LENGTH,
        cint(settings.get("website_route_max_depth")) or DEFAULT_MAX_DEPTH,
    )


def checks_off() -> bool:
    return bool(frappe.flags.in_patch or frappe.flags.in_install or frappe.flags.in_import)


def throw_route_errors(doctype: str, route: str, errors: List[str]) -> None:
    if errors:
        frappe.throw(
            _("Route {0} is not valid:<br>{1}").format(frappe.bold(route), "<br>".join(errors)),
            title=_("{0} Route Not Valid").format(_(doctype)),
        )


def route_owner(route: str, doctype: str, name: str):
    """The Item Group or Website Item, other than `name`, that has `route`."""
    for other in ("Item Group", "Website Item"):
        filters = {"route": route}
        if other == doctype:
            filters["name"] = ("!=", name)
        holder = frappe.db.get_value(other, filters)
        if holder:
            return f"{_(other)} {holder}"
    return None


def throw_if_route_taken(doctype: str, name: str, route: str) -> None:
    holder = route_owner(route, doctype, name)
    if holder:
        frappe.throw(
            _("Route {0} is already used by {1}. Set a different Website Slug.").format(
                frappe.bold(route), holder
            ),
            title=_("Route Already Used"),
        )


def website_item_validate(doc, method=None):
    if checks_off():
        return
    max_length, _depth = get_route_limits()
    template_route = None
    if doc.variant_of:
        template_route = frappe.db.get_value("Website Item", {"item_code": doc.variant_of}, "route")
    category = "" if template_route else frappe.db.get_value("Item Group", doc.item_group, "route") or ""
    doc.route = build_item_route(
        category, doc.item_code, doc.get("website_slug"), cint(doc.has_variants), template_route, max_length
    )
    throw_route_errors("Website Item", doc.route, validate_route(doc.route, max_length))
    throw_if_route_taken("Website Item", doc.name, doc.route)


def website_item_on_update(doc, method=None):
    before = doc.get_doc_before_save()
    old = before.route if before else None
    if not old or old == doc.route:
        return
    apply_redirects([Redirect(old, doc.route, bool(cint(doc.has_variants)))], {old: doc.route}, [doc.route])
    if cint(doc.has_variants):
        enqueue_rebuild()


def web_page_validate(doc, method=None):
    if checks_off() or not doc.route:
        return
    max_length, _depth = get_route_limits()
    throw_route_errors("Web Page", doc.route, validate_route(doc.route, max_length))


def apply_redirects(redirects: List[Redirect], moved: Dict[str, str], live_routes: Iterable[str]) -> dict:
    """Add `redirects`, point the existing redirects to the moved routes, and delete the
    redirects that would hide a live route. Return the counts.

    Rows are written directly. Website Route Redirect is a child table of the Website Settings
    single, so a save from two jobs at the same time could lose rows of the other.
    """
    existing = frappe.get_all("Website Route Redirect", fields=["name", "source", "target"])
    retargeted = retarget_redirects(existing, moved)
    for name, target in retargeted.items():
        frappe.db.set_value("Website Route Redirect", name, "target", target, update_modified=False)

    added = add_redirects([(r.source, r.target) for r in redirects], escaped=True)

    live = list(live_routes)
    sources = [row.source for row in existing] + [r.source for r in redirects]
    hijacking = hijacking_redirects(sources, live)
    if hijacking:
        frappe.db.delete("Website Route Redirect", {"source": ("in", hijacking)})
    return {"added": added, "retargeted": len(retargeted), "deleted": len(hijacking)}


def add_redirects(redirects: List[Tuple[str, str]], escaped: bool = False) -> int:
    """Add (source, target) rows that do not exist. Website Route Redirect sources are
    regular expressions: pass `escaped=False` to escape plain routes, and plain targets get
    a leading "/"."""
    existing = set(frappe.get_all("Website Route Redirect", pluck="source"))
    idx = len(existing)
    added = 0
    for source, target in redirects:
        if not escaped:
            source, target = re.escape(source), "/" + target
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
                "target": target,
            }
        ).db_insert()
        existing.add(source)
        added += 1
    return added


def enqueue_rebuild() -> None:
    """Enqueue `rebuild_routes` after the commit, unless it is already queued or running."""
    if REBUILD_JOB in get_jobs(site=frappe.local.site, key="job_name").get(frappe.local.site, []):
        return
    enqueue(
        "rigpl_erpnext.website_rigpl.route_sync.rebuild_routes",
        job_name=REBUILD_JOB,
        enqueue_after_commit=True,
    )


def rebuild_routes() -> dict:
    """Make the routes of all web groups and Website Items again, with a 301 redirect from
    each changed route. A second run changes nothing. Return the counts."""
    max_length, max_depth = get_route_limits()
    groups = get_groups()
    web_items = frappe.get_all(
        "Website Item",
        fields=["name", "item_code", "item_group", "route", "has_variants", "variant_of", "website_slug"],
    )
    plan = plan_route_rebuild(groups, web_items, max_length, max_depth)

    for name, route in plan.group_routes.items():
        frappe.db.set_value("Item Group", name, "route", route, update_modified=False)
    for name, route in plan.item_routes.items():
        frappe.db.set_value("Website Item", name, "route", route, update_modified=False)

    moved = {r.old: r.new for r in plan.redirects}
    moved.update(old_routes(web_items, plan.item_routes))
    live = live_routes(groups, web_items, plan)
    counts = apply_redirects(plan.redirects, moved, live)

    if plan.errors:
        frappe.log_error("\n".join(plan.errors), "RIGPL website routes not changed")
    if plan.group_routes or plan.item_routes or counts["added"] or counts["deleted"]:
        clear_cache()

    counts.update(
        groups=len(plan.group_routes), website_items=len(plan.item_routes), errors=len(plan.errors)
    )
    return counts


def get_groups() -> List[dict]:
    """All Item Groups. `web` is set for a group shown in the website or with a Website Item."""
    with_items = set(frappe.get_all("Website Item", pluck="item_group"))
    groups = frappe.get_all(
        "Item Group",
        fields=[
            "name",
            "parent_item_group",
            "item_group_name",
            "website_slug",
            "include_in_url",
            "route",
            "show_in_website",
        ],
        order_by="lft",
    )
    for group in groups:
        group["web"] = bool(group.show_in_website) or group.name in with_items
    return groups


def old_routes(web_items: List[dict], item_routes: Dict[str, str]) -> Dict[str, str]:
    return {w["route"]: item_routes[w["name"]] for w in web_items if w["name"] in item_routes and w["route"]}


def live_routes(groups: List[dict], web_items: List[dict], plan) -> List[str]:
    routes = [plan.group_routes.get(g["name"], g["route"]) for g in groups if g["web"]]
    routes += [plan.item_routes.get(w["name"], w["route"]) for w in web_items]
    routes += frappe.get_all("Web Page", filters={"published": 1}, pluck="route")
    return [route for route in routes if route]
