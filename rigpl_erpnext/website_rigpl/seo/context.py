"""
The SEO context that the expressions read (design §6). Only plain dicts, lists and values go
into it, so no object with a write method reaches the sandbox.
"""
from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import cint, get_url, set_request
from frappe.website.context import get_context

from .organization import get_organization, get_public_url
from .sandbox import abs_url, plain_text

PREVIEW_FLAG = "rigpl_seo_preview"
MISSING = object()
# a Web Template with this field shows the latest blog posts
POST_COUNT_FIELD = "blog_count"


def build_variables(web_context: dict, shown_title: str = None) -> dict:
    """`shown_title` is the title of the visible page, when it is not the one of `web_context`."""
    route = get_route(web_context)
    title = web_context.get("title") or ""
    doc = web_context.get("doc")
    website = frappe.get_cached_doc("Website Settings", "Website Settings")
    organization = get_organization()
    return {
        "site": {
            "url": get_url(),
            "name": website.app_name or "",
            "brand": organization["brand"],
            "organization": organization,
        },
        "page": {
            "route": route,
            "url": get_url(route),
            "title": title,
            "parents": to_plain(web_context.get("parents") or []),
            "h1": remove_prefix(title, web_context.get("title_prefix")),
            "crumbs": get_crumbs(web_context, shown_title),
        },
        "doc": to_plain(doc) if doc else {},
        "item": {},
        "variants": [],
        "common": [],
        "block": {},
        "nav": {"top_bar": get_top_bar(web_context)},
    }


def get_crumbs(web_context: dict, shown_title: str = None) -> list:
    """The items of the visible breadcrumb, as `templates/includes/breadcrumbs.html` shows them:
    the last three parents, then the page (#264)."""
    parents = web_context.get("parents") or []
    if web_context.get("no_breadcrumbs") or not parents:
        return []
    crumbs = [(get_label(row), get_crumb_url(row.get("route"))) for row in parents[-3:]]
    title = shown_title or web_context.get("title")
    crumbs.append((title, get_url(get_route(web_context))))
    return make_links(crumbs)


def get_label(row) -> str:
    return row.get("title") or row.get("label") or row.get("name") or ""


def get_crumb_url(route: str) -> str:
    # "index" is the address of the home page
    route = (route or "").strip()
    return get_url("/") if route.strip("/") in ("", "index") else abs_url(route)


def get_top_bar(web_context: dict) -> list:
    """The links of the top bar. A row that only opens a menu has no link."""
    rows = web_context.get("top_bar_items") or []
    links = [(row.get("label"), (row.get("url") or "").strip()) for row in rows]
    return make_links([(label, abs_url(url)) for label, url in links if url and url != "#"])


def make_links(pairs: list) -> list:
    return [
        {"position": position, "name": plain_text(name), "url": url}
        for position, (name, url) in enumerate(pairs, 1)
    ]


def get_blocks(doc) -> list:
    """The visible blocks of a Web Page for `block` (#269). Each block has its field values and
    the public records that the fields link to: `products`, `slides` and `posts`."""
    rows = (doc.get("page_blocks") if doc else None) or []
    pairs = [make_block(row) for row in rows if not row.get("hide_block")]
    products = get_products([name for _, links in pairs for name in links.get("Website Item", [])])
    for block, links in pairs:
        found = [products[name] for name in links.get("Website Item", []) if name in products]
        block["products"] = [dict(row, position=position) for position, row in enumerate(found, 1)]
        block["slides"] = [
            slide for name in links.get("Website Slideshow", []) for slide in get_slides(name)
        ]
    return [block for block, _ in pairs]


def make_block(row) -> tuple:
    """The block and the names that its Link fields hold, by DocType."""
    fields = frappe.get_cached_doc("Web Template", row.get("web_template")).fields
    values = frappe.parse_json(row.get("web_template_values") or "{}") or {}
    block = dict(values, idx=row.get("idx"), web_template=row.get("web_template"), posts=[])
    if any(field.fieldname == POST_COUNT_FIELD for field in fields):
        block["posts"] = get_posts(values.get(POST_COUNT_FIELD))
    return block, get_links(fields, values)


def get_links(fields: list, values: dict) -> dict:
    links = {}
    table = None
    for field in fields:
        if field.fieldtype in ("Table Break", "Section Break"):
            table = field.fieldname if field.fieldtype == "Table Break" else None
            continue
        if field.fieldtype != "Link":
            continue
        sources = (values.get(table) or []) if table else [values]
        names = [source.get(field.fieldname) for source in sources]
        links.setdefault(field.options, []).extend(name for name in names if name)
    return links


def get_products(names: list) -> dict:
    """The published Website Items of `names`, in one query."""
    if not names:
        return {}
    rows = frappe.get_all(
        "Website Item",
        filters={"name": ["in", names], "published": 1},
        fields=["name", "item_code", "web_item_name", "route", "website_image"],
    )
    return {
        row.name: {
            "name": row.name,
            "item_code": row.item_code,
            "title": row.web_item_name,
            "url": abs_url(row.route),
            "image": get_public_url(row.website_image),
        }
        for row in rows
    }


def get_slides(name: str) -> list:
    if not frappe.db.exists("Website Slideshow", name):
        return []
    return [
        {
            "idx": row.idx,
            "image": get_public_url(row.image),
            "heading": plain_text(row.heading),
            "description": plain_text(row.description),
            "url": abs_url(row.url),
        }
        for row in frappe.get_cached_doc("Website Slideshow", name).slideshow_items
    ]


def get_posts(count) -> list:
    """The posts that the web template shows: same order and limit."""
    rows = frappe.get_all(
        "Blog Post",
        filters={"published": 1},
        fields=["title", "route", "blogger", "blog_intro", "published_on", "meta_image"],
        order_by="modified desc",
        limit=min(max(cint(count or 3), 1), 12),
    )
    bloggers = [row.blogger for row in rows if row.blogger]
    filters = {"name": ["in", bloggers]}
    authors = frappe.get_all("Blogger", filters=filters, fields=["name", "full_name"]) if bloggers else []
    names = {author.name: author.full_name for author in authors}
    return [
        {
            "position": position,
            "title": row.title,
            "url": abs_url(row.route),
            "author": names.get(row.blogger) or "",
            "description": plain_text(row.blog_intro),
            "published_on": str(row.published_on or ""),
            "image": get_public_url(row.meta_image),
        }
        for position, row in enumerate(rows, 1)
    ]


def get_route(web_context: dict) -> str:
    # Blog Post pages overwrite `route` with "blog", but `path` stays the address of the page
    return (web_context.get("path") or web_context.get("route") or "").lstrip("/")


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
