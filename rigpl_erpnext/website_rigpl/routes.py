"""
Website route rules (#97).

The v13 migration copied the v12 Item routes to Website Item, and v12 variants used the
route of their template. So many Website Items share one route, and the router shows
whichever comes first. `plan_shared_route_fixes` gives each of them a route of its own.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from frappe.website.utils import cleanup_page_name


def slugify(text: str) -> str:
    """The same slug as WebsiteGenerator.scrub."""
    return cleanup_page_name(text).replace("_", "-")


def plan_shared_route_fixes(
    web_items: List[dict], item_routes: Dict[str, str]
) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    """Return ({website item name: new route}, [(old route, redirect target)]).

    For each route that more than one Website Item uses:
    - One template keeps the route: the one whose Item has the same route (the v12
      owner), else the first by name. Other templates get `<parent path>/<item code slug>`.
    - Each variant gets `<route of its template Website Item>/<item code slug>`.
    - A route that no template keeps redirects to the template of its variants.

    `web_items` rows need name, item_code, route, has_variants and variant_of.
    `item_routes` maps a template item code to its Item route.
    """
    by_route = defaultdict(list)
    for row in web_items:
        if row["route"]:
            by_route[row["route"]].append(row)
    shared = {route: rows for route, rows in by_route.items() if len(rows) > 1}

    new_routes: Dict[str, str] = {}
    for route, rows in shared.items():
        templates = sorted((r for r in rows if r["has_variants"]), key=lambda r: r["name"])
        owner = next((t for t in templates if item_routes.get(t["item_code"]) == route), None)
        owner = owner or (templates[0] if templates else None)
        for template in templates:
            if template is not owner:
                new_routes[template["name"]] = join_route(parent_path(route), template["item_code"])

    template_route = {
        row["item_code"]: new_routes.get(row["name"], row["route"])
        for row in web_items
        if row["has_variants"]
    }

    redirects = []
    for route, rows in shared.items():
        variants = [r for r in rows if not r["has_variants"]]
        for variant in variants:
            base = template_route.get(variant["variant_of"]) or parent_path(route)
            new_routes[variant["name"]] = join_route(base, variant["item_code"])

        if not any(r["has_variants"] for r in rows) and variants:
            target = template_route.get(variants[0]["variant_of"])
            if target and target != route:
                redirects.append((route, target))

    assert_unique_routes(web_items, new_routes)
    return new_routes, redirects


def parent_path(route: str) -> str:
    return route.rsplit("/", 1)[0] if "/" in route else ""


def join_route(base: str, item_code: str) -> str:
    slug = slugify(item_code)
    return f"{base}/{slug}" if base else slug


def assert_unique_routes(web_items: List[dict], new_routes: Dict[str, str]) -> None:
    """Fail before any write if the plan would make a new shared route."""
    final = [new_routes.get(row["name"], row["route"]) for row in web_items if row["route"]]
    seen = set()
    for route in final:
        if route in seen:
            raise ValueError(f"Route fix would give two Website Items the route {route!r}")
        seen.add(route)
