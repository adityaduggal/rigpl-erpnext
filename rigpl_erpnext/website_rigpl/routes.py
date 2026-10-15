"""
Website route rules (#97). The functions in this file do not read the database.

- Category (Item Group): the slugs of the ancestors with Include in URL, then its own slug.
- Template or item without variants: `<category route>/<slug>`. The slug is the Website Slug
  of the Website Item, or the item code cut to fit the length limit.
- Variant: `<template route>/<item code>`.

A route uses only a-z, 0-9 and "-", has at most `max_length` characters, and the category
part has at most `max_depth` segments. The limits are in RIGPL Settings.

`plan_shared_route_fixes` is the earlier repair (#99) for Website Items that shared a route.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

DEFAULT_MAX_LENGTH = 75
DEFAULT_MAX_DEPTH = 2
# Variant item codes are 11 or 12 characters (dev-rigpl-v12, 2026-10-15).
MAX_ITEM_CODE_LEN = 12
# A category route must leave at least this many characters for a template slug.
MIN_TEMPLATE_SLUG = 30

SEGMENT = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PREFIX_SUFFIX = r"(/.*)?"


def slugify(text: str) -> str:
    """Lower case; each run of other characters becomes one "-". "4.1-to-8mm" is "4-1-to-8mm"."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def validate_route(route: str, max_length: int) -> List[str]:
    """Return the rules that `route` breaks. An empty list means the route is valid."""
    if not route:
        return ["The route is empty."]
    errors = []
    if len(route) > max_length:
        errors.append(f"The route has {len(route)} characters. The maximum is {max_length}.")
    if not all(SEGMENT.match(segment) for segment in route.split("/")):
        errors.append(
            "Each part of the route must use only a-z, 0-9 and single hyphens, "
            "and must not start or end with a hyphen."
        )
    return errors


def cut_slug(slug: str, max_len: int) -> str:
    """Cut `slug` at word boundaries to at most `max_len` characters.

    Keep the first word (the series, for example "122"), then as many words from the end as
    fit, then words after the first. Templates of one series differ at the end (Metric/BSW,
    size range), so a cut at the end would give them the same slug.
    """
    if len(slug) <= max_len:
        return slug
    words = slug.split("-")
    head, tail = [words[0]], []
    first, last = 1, len(words) - 1
    while last >= first and fits(head + [words[last]] + tail, max_len):
        tail.insert(0, words[last])
        last -= 1
    while first <= last and fits(head + [words[first]] + tail, max_len):
        head.append(words[first])
        first += 1
    return "-".join(head + tail)[:max_len].strip("-")


def fits(words: List[str], max_len: int) -> bool:
    return len("-".join(words)) <= max_len


def group_slug(group: dict) -> str:
    return slugify(group.get("website_slug") or group.get("item_group_name") or group["name"])


def build_group_route(chain: List[dict], max_depth: int) -> str:
    """`chain` is the groups from below the root to this group. Raise ValueError if the
    route has more than `max_depth` segments."""
    *ancestors, group = chain
    segments = [group_slug(a) for a in ancestors if a.get("include_in_url")]
    segments.append(group_slug(group))
    if len(segments) > max_depth:
        raise ValueError(
            f"The category route {'/'.join(segments)} has {len(segments)} parts. "
            f"The maximum is {max_depth}. Clear Include in URL on an ancestor group."
        )
    return "/".join(segments)


def template_slug_budget(category_route: str, max_length: int) -> int:
    """Characters left for a template slug, so that its variant routes also fit."""
    return max_length - len(category_route) - 2 - MAX_ITEM_CODE_LEN


def check_group_budget(route: str, max_length: int) -> List[str]:
    budget = template_slug_budget(route, max_length)
    if budget >= MIN_TEMPLATE_SLUG:
        return []
    return [
        f"The category route {route} leaves {budget} characters for a template name. "
        f"The minimum is {MIN_TEMPLATE_SLUG}. Use a shorter Website Slug."
    ]


def build_item_route(
    category_route: str,
    item_code: str,
    website_slug: Optional[str],
    has_variants: bool,
    template_route: Optional[str],
    max_length: int,
) -> str:
    """The route of a Website Item. A variant needs the route of its template Website Item."""
    if template_route:
        return f"{template_route}/{slugify(website_slug or item_code)}"
    if website_slug:
        slug = slugify(website_slug)
    elif has_variants:
        slug = cut_slug(slugify(item_code), template_slug_budget(category_route, max_length))
    else:
        slug = cut_slug(slugify(item_code), max_length - len(category_route) - 1)
    return f"{category_route}/{slug}" if category_route else slug


class Redirect(NamedTuple):
    old: str
    new: str
    prefix: bool  # also redirect the routes below `old`, for example the variants of a template

    @property
    def source(self) -> str:
        return re.escape(self.old) + (PREFIX_SUFFIX if self.prefix else "")

    @property
    def target(self) -> str:
        return "/" + self.new + (r"\1" if self.prefix else "")


class RoutePlan(NamedTuple):
    group_routes: Dict[str, str]  # {item group: new route}, changed routes only
    item_routes: Dict[str, str]  # {website item: new route}, changed routes only
    redirects: List[Redirect]
    errors: List[str]  # a document with an error keeps its route


def plan_route_rebuild(
    groups: List[dict], web_items: List[dict], max_length: int, max_depth: int
) -> RoutePlan:
    """Calculate the routes of all web groups and Website Items again.

    `groups` rows: name, parent_item_group, item_group_name, website_slug, include_in_url,
    route, and `web` (shown in the website or has a Website Item). A root group (no parent)
    and a group that is not `web` keep their route.
    `web_items` rows: name, item_code, item_group, route, has_variants, variant_of, website_slug.
    """
    by_name = {g["name"]: g for g in groups}
    errors: List[str] = []
    taken: Dict[str, str] = {}
    final_group: Dict[str, str] = {}

    for group in groups:
        old = group.get("route") or ""
        new = None
        if group.get("web") and group.get("parent_item_group"):
            new = new_group_route(group, by_name, max_length, max_depth, errors)
            new = take_route(new, group["name"], taken, errors)
        if not new:
            take_route(old, group["name"], taken, [])
        final_group[group["name"]] = new or old

    final_item: Dict[str, str] = {}
    template_codes = {w["item_code"]: w["name"] for w in web_items if w.get("has_variants")}
    ordered = sorted(web_items, key=lambda w: bool(w.get("variant_of")))
    for web_item in ordered:
        template = template_codes.get(web_item.get("variant_of"))
        template_route = final_item.get(template) if template else None
        category = final_group.get(web_item.get("item_group"), "")
        new = build_item_route(
            category,
            web_item["item_code"],
            web_item.get("website_slug"),
            bool(web_item.get("has_variants")),
            template_route,
            max_length,
        )
        broken = validate_route(new, max_length)
        if broken:
            errors.append(f"Website Item {web_item['name']}: {new}: {' '.join(broken)}")
            new = None
        old = web_item.get("route") or ""
        new = take_route(new, web_item["name"], taken, errors)
        if not new:
            take_route(old, web_item["name"], taken, [])
        final_item[web_item["name"]] = new or old

    group_routes = changed(groups, final_group)
    item_routes = changed(web_items, final_item)
    redirects = plan_redirects(groups, web_items, group_routes, item_routes, template_codes)
    return RoutePlan(group_routes, item_routes, redirects, errors)


def new_group_route(group, by_name, max_length, max_depth, errors) -> Optional[str]:
    try:
        route = build_group_route(group_chain(group, by_name), max_depth)
    except ValueError as e:
        errors.append(f"Item Group {group['name']}: {e}")
        return None
    broken = validate_route(route, max_length) + check_group_budget(route, max_length)
    if broken:
        errors.append(f"Item Group {group['name']}: {route}: {' '.join(broken)}")
        return None
    return route


def group_chain(group: dict, by_name: Dict[str, dict]) -> List[dict]:
    """The groups from below the root to `group`. The root is not part of a route."""
    chain = [group]
    parent = by_name.get(group.get("parent_item_group"))
    while parent and parent.get("parent_item_group"):
        chain.insert(0, parent)
        parent = by_name.get(parent.get("parent_item_group"))
    return chain


def take_route(route: Optional[str], owner: str, taken: Dict[str, str], errors: List[str]) -> Optional[str]:
    """Reserve `route` for `owner`. Return None if another document has it."""
    if not route:
        return None
    holder = taken.get(route)
    if holder and holder != owner:
        errors.append(f"{owner}: the route {route} is already used by {holder}.")
        return None
    taken[route] = owner
    return route


def changed(rows: List[dict], final: Dict[str, str]) -> Dict[str, str]:
    return {r["name"]: final[r["name"]] for r in rows if final[r["name"]] != (r.get("route") or "")}


def plan_redirects(groups, web_items, group_routes, item_routes, template_codes) -> List[Redirect]:
    """One redirect for each changed route that was in use.

    If all variants of a template moved with it, one prefix redirect of the template covers
    them. Else each route gets an exact redirect: Frappe tries the redirects in no fixed
    order, so a prefix redirect must not match a variant that moved elsewhere.
    """
    old_group = {g["name"]: g.get("route") or "" for g in groups}
    old_item = {w["name"]: w.get("route") or "" for w in web_items}

    def final(name):
        return item_routes.get(name, old_item[name])

    covered, not_covered = set(), set()
    for web_item in web_items:
        template = template_codes.get(web_item.get("variant_of"))
        if not template or not old_item[web_item["name"]]:
            continue
        old_template = old_item[template]
        if moved_with_template(old_item[web_item["name"]], final(web_item["name"]), old_template, final(template)):
            covered.add(web_item["name"])
        elif old_template and old_item[web_item["name"]].startswith(old_template + "/"):
            not_covered.add(template)

    redirects = [Redirect(old_group[name], new, False) for name, new in group_routes.items() if old_group[name]]
    for web_item in web_items:
        name = web_item["name"]
        old = old_item[name]
        if name not in item_routes or not old:
            continue
        template = template_codes.get(web_item.get("variant_of"))
        if name in covered and template not in not_covered and template in item_routes:
            continue
        prefix = bool(web_item.get("has_variants")) and name not in not_covered
        redirects.append(Redirect(old, item_routes[name], prefix))
    return redirects


def moved_with_template(old: str, new: str, old_template: str, new_template: Optional[str]) -> bool:
    if not new_template or not old_template or not old.startswith(old_template + "/"):
        return False
    return new == new_template + old[len(old_template):]


def retarget_redirects(existing: List[dict], moved: Dict[str, str]) -> Dict[str, str]:
    """Return {redirect row name: new target} for the rows whose target route moved, so a
    visitor gets one 301, not a chain."""
    updates = {}
    for row in existing:
        target = row.get("target") or ""
        suffix = r"\1" if target.endswith(r"\1") else ""
        base = target[1 : len(target) - len(suffix)] if target.startswith("/") else ""
        if base in moved:
            updates[row["name"]] = "/" + moved[base] + suffix
    return updates


def hijacking_redirects(sources: Iterable[str], live_routes: Iterable[str]) -> List[str]:
    """The redirect sources that match a live route. Frappe resolves redirects before pages,
    so such a redirect would hide the page."""
    live = list(live_routes)
    found = []
    for source in sources:
        try:
            pattern = re.compile(source.strip("/ ") + "$")
        except re.error:
            continue
        if any(pattern.match(route) for route in live):
            found.append(source)
    return found


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
