"""
The SEO context that the expressions read (design §6). Only plain dicts, lists and values go
into it, so no object with a write method reaches the sandbox.
"""
from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import get_url, set_request
from frappe.website.context import get_context

PREVIEW_FLAG = "rigpl_seo_preview"
MISSING = object()


def build_variables(web_context: dict) -> dict:
    route = get_route(web_context)
    title = web_context.get("title") or ""
    doc = web_context.get("doc")
    website = frappe.get_cached_doc("Website Settings", "Website Settings")
    return {
        "site": {"url": get_url(), "name": website.app_name or ""},
        "page": {
            "route": route,
            "url": get_url(route),
            "title": title,
            "parents": to_plain(web_context.get("parents") or []),
            "h1": remove_prefix(title, web_context.get("title_prefix")),
        },
        "doc": to_plain(doc) if doc else {},
        "item": {},
        "variants": [],
        "common": [],
        "block": {},
        "nav": {},
    }


def get_route(web_context: dict) -> str:
    return (web_context.get("route") or web_context.get("path") or "").lstrip("/")


def remove_prefix(title: str, prefix: str) -> str:
    """Frappe puts the Website Settings title prefix before the title. The H1 does not have it."""
    start = "{} - ".format(prefix)
    return title[len(start) :] if prefix and title.startswith(start) else title


def get_route_context(route: str) -> dict:
    """The website context of a published route as a Guest sees it (D9), outside a website
    request. An empty route is the home page of Website Settings."""
    route = (route or "").strip().strip("/")
    route = route or frappe.db.get_single_value("Website Settings", "home_page") or "login"
    saved = {name: getattr(frappe.local, name, MISSING) for name in ("request", "path", "no_cache")}
    preview_flag = frappe.flags.get(PREVIEW_FLAG)
    session = frappe.local.session
    user, sid, data, form_dict = session.user, session.sid, session.data, frappe.local.form_dict
    try:
        # a Website Item page as a desk user can make a Customer and a Contact for that user
        frappe.set_user("Guest")
        set_request(method="GET", path="/" + route)
        frappe.local.path = route
        frappe.local.no_cache = 1  # a preview must not fill the page cache
        frappe.flags[PREVIEW_FLAG] = True
        return get_context(route)
    except (frappe.PageDoesNotExistError, frappe.DoesNotExistError, frappe.Redirect):
        frappe.throw(
            "{} is not a published page".format(frappe.utils.escape_html(route)),
            frappe.PageDoesNotExistError,
        )
    finally:
        frappe.set_user(user)
        session.sid, session.data, frappe.local.form_dict = sid, data, form_dict
        frappe.flags[PREVIEW_FLAG] = preview_flag
        for name, value in saved.items():
            if value is not MISSING:
                setattr(frappe.local, name, value)
            elif hasattr(frappe.local, name):
                delattr(frappe.local, name)


def to_plain(value):
    if isinstance(value, Document):
        value = value.as_dict()
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value
