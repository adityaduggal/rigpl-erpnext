"""
The meta tags of a page from SEO Settings and SEO Rules (#261). Last wins: SEO Settings,
SEO Rule, the document fields, Website Route Meta.
"""
from __future__ import annotations

from fnmatch import fnmatchcase
from html import unescape
from typing import Iterable, List, Optional

import frappe
from frappe.utils import cint, escape_html
from frappe.website.render import clear_cache
from jinja2 import TemplateSyntaxError

from . import context as seo_context
from .builder import BuildError
from .sandbox import abs_url, check_template, plain_text, render_text

RULE_DOCTYPE = "SEO Rule"
SETTINGS_DOCTYPE = "SEO Settings"
RULES_CACHE_KEY = "rigpl_seo_rules"
TEMPLATE_FIELDS = ("title", "description", "canonical", "robots", "og_type", "image")
SETTINGS_FIELDS = ("title", "description")
DOCUMENT_FIELDS = {"title": "meta_title", "description": "meta_description", "image": "meta_image"}
DEFAULT_LIMITS = {"title": 60, "description": 160}


def find_rule(doctype: Optional[str], route: str):
    """The enabled SEO Rule with the highest priority that matches, else None."""
    matches = [rule for rule in get_rules() if is_match(rule, doctype, route)]
    if not matches:
        return None

    def rank(rule):
        has_both = bool(rule.reference_doctype and rule.route_pattern)
        return -cint(rule.priority), not has_both, rule.name

    return frappe.get_cached_doc(RULE_DOCTYPE, min(matches, key=rank).name)


def build_meta(web_context: dict, rule, errors: List[BuildError]) -> dict:
    """The changed values of `title`, `canonical` and `metatags`."""
    return PageMeta(web_context, rule, errors).build()


def get_rules() -> list:
    def read_rules():
        fields = ["name", "priority", "reference_doctype", "route_pattern"]
        return frappe.get_all(RULE_DOCTYPE, filters={"enabled": 1}, fields=fields)

    return frappe.cache().get_value(RULES_CACHE_KEY, generator=read_rules)


def is_match(rule, doctype: Optional[str], route: str) -> bool:
    if rule.reference_doctype and rule.reference_doctype != doctype:
        return False
    if rule.route_pattern and not fnmatchcase(route, rule.route_pattern):
        return False
    return bool(rule.reference_doctype or rule.route_pattern)


def get_settings():
    return frappe.get_cached_doc(SETTINGS_DOCTYPE, SETTINGS_DOCTYPE)


def get_limit(field: str) -> int:
    return cint(get_settings().get(field + "_limit")) or DEFAULT_LIMITS[field]


def check_templates(doc, fields: Iterable[str]) -> None:
    for field in fields:
        try:
            check_template(doc.get(field))
        except TemplateSyntaxError as e:
            frappe.throw("{}: {}".format(doc.meta.get_label(field), escape_html(str(e))))


def clear_rule_cache(path=None) -> None:
    """Also the `website_clear_cache` hook, which passes a path."""
    frappe.cache().delete_value(RULES_CACHE_KEY)


def clear_caches() -> None:
    clear_rule_cache()
    clear_cache()


class PageMeta:
    def __init__(self, web_context: dict, rule, errors: List[BuildError]):
        self.context = web_context
        self.rule = rule
        self.errors = errors
        self.settings = get_settings()
        self.original = dict(web_context.get("metatags") or {})
        self.tags = dict(self.original)
        self.changes = {}
        self._variables = None

    def build(self) -> dict:
        self.set_rule_values()
        if self.settings.site_name:
            self.tags["og:site_name"] = self.settings.site_name
        self.set_route_meta()
        if self.tags != self.original:
            self.changes["metatags"] = frappe._dict(self.tags)
        return self.changes

    def set_rule_values(self) -> None:
        for field, setter in (
            ("title", self.set_title),
            ("description", self.set_description),
            ("image", self.set_image),
            ("canonical", self.set_canonical),
        ):
            value = self.value(field)
            if value:
                setter(value)

        robots = self.rendered(self.rule, "robots")
        # a page controller sets noindex for a reason, so a rule cannot remove it
        if robots and "noindex" not in str(self.tags.get("robots") or "").lower():
            self.tags["robots"] = robots
        og_type = self.rendered(self.rule, "og_type")
        if og_type:
            self.tags["og:type"] = og_type
        if self.rule and self.rule.twitter_card:
            self.tags["twitter:card"] = self.rule.twitter_card

    def value(self, field: str) -> str:
        """The document field replaces a rule or settings value. It does not act alone."""
        value = self.rendered(self.rule, field)
        if not value and field in SETTINGS_FIELDS:
            value = self.rendered(self.settings, field)
        if not value:
            return ""
        doc = self.context.get("doc")
        own = doc.get(DOCUMENT_FIELDS[field]) if doc and field in DOCUMENT_FIELDS else None
        return str(own or "").strip() or value

    def rendered(self, source_doc, field: str) -> str:
        source = source_doc.get(field + "_template") if source_doc else None
        if not source:
            return ""
        try:
            return render_text(source, self.variables)
        except Exception as e:
            message = "{}: {}".format(type(e).__name__, e)
            self.errors.append(BuildError(source_doc.name, field, message))
            return ""

    @property
    def variables(self) -> dict:
        if self._variables is None:
            self._variables = seo_context.build_variables(self.context)
        return self._variables

    def set_title(self, value: str) -> None:
        title = clean_title(value)
        if not title:
            return
        self.changes["title"] = title
        keys = ["title", "og:title", "twitter:title"]
        # Web Page and Blog Post give the title as `name`
        if "name" in self.tags:
            keys.append("name")
        self.tags.update(dict.fromkeys(keys, title))

    def set_description(self, value: str) -> None:
        description = cut(plain_text(value), get_limit("description"))
        if description:
            keys = ("description", "og:description", "twitter:description")
            self.tags.update(dict.fromkeys(keys, description))

    def set_image(self, value: str) -> None:
        keys = ("image", "og:image", "twitter:image")
        self.tags.update(dict.fromkeys(keys, abs_url(value)))
        self.tags["twitter:card"] = "summary_large_image"

    def set_canonical(self, value: str) -> None:
        url = abs_url(value)
        self.changes["canonical"] = self.tags["url"] = self.tags["og:url"] = url

    def set_route_meta(self) -> None:
        """Frappe applies Website Route Meta before the hook, so it is applied again."""
        route_tags = get_route_tags(self.context.get("path"))
        for key, setter in (
            ("title", self.set_title),
            ("description", self.set_description),
            ("image", self.set_image),
        ):
            if route_tags.get(key):
                setter(route_tags[key])
        # the exact text of the row stays, also above the limit
        self.tags.update(route_tags)


def get_route_tags(route: Optional[str]) -> dict:
    if route == "":
        route = frappe.db.get_single_value("Website Settings", "home_page")
    if not route or route.endswith((".js", ".css")):
        return {}
    if not frappe.db.exists("Website Route Meta", route):
        return {}
    tags = {}
    for row in frappe.get_cached_doc("Website Route Meta", route).meta_tags:
        tags.update(row.get_meta_dict())
    return tags


def clean_title(value: str) -> str:
    """Plain text: the `<title>` block of Frappe decodes entities and does not escape."""
    text = str(value)
    while unescape(text) != text:
        text = unescape(text)
    return plain_text(text).replace("<", "").replace(">", "")


def cut(text: str, limit: int) -> str:
    """At most `limit` characters, cut at a word."""
    if len(text) <= limit:
        return text
    head = text[: limit + 1]
    return (head.rsplit(" ", 1)[0] if " " in head else head[:limit]).rstrip(" ,;:-")
