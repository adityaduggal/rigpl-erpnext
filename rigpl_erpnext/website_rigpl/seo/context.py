"""
The SEO context that the expressions read (design §6). Only plain dicts, lists and values go
into it, so no object with a write method reaches the sandbox.
"""
from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, get_url, nowdate, set_request
from frappe.website.context import get_context

from ..catalog import get_attribute_values, get_list_prices, get_stock_qty, get_variant_table
from ..compat import get_ecommerce
from ...utils.item_attribute_utils import get_template_attributes
from .organization import get_organization, get_public_url
from .sandbox import abs_url, plain_text

PREVIEW_FLAG = "rigpl_seo_preview"
MISSING = object()
# a Web Template with this field shows the latest blog posts
POST_COUNT_FIELD = "blog_count"
# above this number of variants, a variant has only its address and its code
DEFAULT_VARIANT_LIMIT = 200
SCHEMA = "https://schema.org/"


def build_variables(web_context: dict, shown_title: str = None) -> dict:
    """`shown_title` is the H1 that the page shows, when it is not the title of `web_context`."""
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
            "h1": shown_title or remove_prefix(title, web_context.get("title_prefix")),
            "crumbs": get_crumbs(web_context, shown_title),
        },
        "doc": to_plain(doc) if doc else {},
        "item": {},
        "variants": [],
        "common": [],
        "listing": [],
        "block": {},
        "nav": {"top_bar": get_top_bar(web_context)},
    }


def get_catalog(doc) -> dict:
    """`item`, `variants`, `common` and `listing` of a product or category page (#265).
    The prices are the prices that a visitor who is not logged in sees (D9)."""
    values = {"item": {}, "variants": [], "common": [], "listing": []}
    doctype = doc.get("doctype") if doc else None
    if doctype == "Website Item" and doc.get("item_code"):
        reader = get_template_values if doc.get("has_variants") else get_product_values
        values.update(reader(doc))
    elif doctype == "Item Group":
        values["listing"] = get_listing(doc.get("name"))
    return values


def get_template_values(doc) -> dict:
    table = get_variant_table(doc.get("name"))
    rows = table["rows"]
    codes = [row["item_code"] for row in rows]
    limit = cint(frappe.get_cached_doc("SEO Settings", "SEO Settings").get("variant_limit"))
    full = len(rows) <= (limit or DEFAULT_VARIANT_LIMIT)
    items = get_variant_items(codes) if full else {}
    offers = Offers(codes, doc.get("item_code")) if full else None
    variants = [
        make_variant(row, table["columns"], items.get(row["item_code"]), offers) for row in rows
    ]
    common = [{"name": label, "value": value} for label, value in table["common"]]
    item = make_item(doc, is_template=True, properties=common)
    item["varies_by"] = [column["label"] for column in table["columns"]]
    return {"item": item, "variants": variants, "common": common}


def get_variant_items(codes: list) -> dict:
    if not codes:
        return {}
    fields = ["item_code", "web_item_name", "website_image"]
    rows = frappe.get_all("Website Item", filters={"item_code": ["in", codes]}, fields=fields)
    return {row.item_code: row for row in rows}


def make_variant(row: dict, columns: list, web_item, offers) -> dict:
    """With no `offers`, the variant is above the variant limit: it has only its address and code."""
    url = abs_url(row["route"])
    variant = {"id": url + "#product", "sku": row["item_code"], "url": url, "full": bool(offers)}
    properties = []
    if offers:
        properties = [
            {"name": column["label"], "value": row["values"][column["attribute"]]}
            for column in columns
            if row["values"][column["attribute"]]
        ]
    variant.update(
        name=(web_item and web_item.web_item_name) or "",
        image=get_public_url(web_item and web_item.website_image),
        size=", ".join("{name} {value}".format(**prop) for prop in properties),
        properties=properties,
        offer=offers.get(row["item_code"], url, row["shop"]["stock_value"]) if offers else None,
    )
    return variant


def get_product_values(doc) -> dict:
    """A variant, or a product that has no variants."""
    code, template = doc.get("item_code"), doc.get("variant_of")
    parent = None
    if template:
        filters = {"item_code": template, "published": 1}
        fields = ["item_code", "web_item_name", "route", "website_warehouse"]
        parent = frappe.db.get_value("Website Item", filters, fields, as_dict=True)
    item = make_item(doc, is_template=False, properties=get_properties(code, template))
    warehouse = doc.get("website_warehouse") or (parent and parent.website_warehouse)
    qty = get_stock_qty({code: warehouse}).get(code, 0)
    item["offer"] = Offers([code], template).get(code, item["url"], qty)
    if parent:
        url = abs_url(parent.route)
        item["parent"] = {
            "id": url + "#product",
            "url": url,
            "name": parent.web_item_name,
            "code": parent.item_code,
        }
    return {"item": item}


def make_item(doc, is_template: bool, properties: list) -> dict:
    url = abs_url(doc.get("route"))
    description = doc.get("web_long_description") or doc.get("description") or ""
    return {
        "is_template": is_template,
        "id": url + "#product",
        "url": url,
        "name": doc.get("web_item_name") or "",
        "code": doc.get("item_code"),
        "image": get_public_url(doc.get("website_image")),
        # a space keeps the words of two HTML blocks apart
        "description": plain_text(description.replace("><", "> <")),
        "category": doc.get("item_group") or "",
        "properties": properties,
        "varies_by": [],
        "parent": None,
        "offer": None,
    }


def get_properties(code: str, template: str) -> list:
    if not template:
        return []
    attributes = get_template_attributes(template)
    rows = get_attribute_values([code], [row["attribute"] for row in attributes])
    values = {row["attribute"]: row["attribute_value"] for row in rows}
    return [
        {"name": row["label"], "value": values[row["attribute"]]}
        for row in attributes
        if values.get(row["attribute"])
    ]


class Offers:
    """The offers of some items of one page. The prices, the shipping rules and the settings
    are read one time."""

    def __init__(self, codes: list, template: str = None):
        cart = get_ecommerce("get_shopping_cart_settings")()
        shows_price = cart.enabled and cart.show_price and not cart.hide_price_for_guest
        self.template = template
        self.prices = get_list_prices(codes, template or "", cart.price_list) if shows_price else {}
        self.settings = frappe.get_cached_doc("SEO Settings", "SEO Settings")
        self.rules = get_shipping_rules() if self.prices else []

    def get(self, code: str, url: str, qty) -> dict | None:
        """None when a visitor sees no price."""
        price = self.prices.get(code) or self.prices.get(self.template)
        if not price:
            return None
        rate = flt(price.price_list_rate)
        return {
            "price": rate,
            "currency": price.currency,
            "availability": SCHEMA + ("InStock" if flt(qty) > 0 else "BackOrder"),
            "condition": SCHEMA + "NewCondition",
            "url": url,
            "valid_until": self.valid_until(price),
            "shipping": self.shipping(rate),
        }

    def valid_until(self, price) -> str:
        if price.get("valid_upto"):
            return str(price.valid_upto)
        days = cint(self.settings.get("price_valid_days"))
        return str(add_days(nowdate(), days)) if days else ""

    def shipping(self, amount: float) -> list:
        """One row for each country of each Shipping Rule that has a charge for `amount`."""
        handling, transit = self.days("handling"), self.days("transit")
        found = []
        for rule in self.rules:
            charge = get_shipping_charge(rule, amount)
            if charge is None:
                continue
            for country in rule["countries"]:
                found.append(
                    {
                        "country": country,
                        "rate": charge,
                        "currency": rule["currency"],
                        "handling": handling,
                        "transit": transit,
                    }
                )
        return found

    def days(self, kind: str) -> dict:
        maximum = cint(self.settings.get(kind + "_days_max"))
        if not maximum:
            return {}
        minimum = cint(self.settings.get(kind + "_days_min"))
        return {"min": minimum, "max": maximum, "unit": "DAY"}


def get_shipping_rules() -> list:
    """The enabled Selling Shipping Rules that have countries. A rule by weight is not used."""
    filters = {
        "disabled": 0,
        "shipping_rule_type": "Selling",
        "calculate_based_on": ["in", ["Fixed", "Net Total"]],
    }
    fields = ["name", "company", "shipping_amount", "calculate_based_on"]
    rules = frappe.get_all("Shipping Rule", filters=filters, fields=fields, order_by="name")
    if not rules:
        return []
    in_rules = {"parent": ["in", [rule.name for rule in rules]], "parenttype": "Shipping Rule"}
    countries = frappe.get_all("Shipping Rule Country", filters=in_rules, fields=["parent", "country"])
    conditions = frappe.get_all(
        "Shipping Rule Condition",
        filters=in_rules,
        fields=["parent", "from_value", "to_value", "shipping_amount"],
        order_by="from_value",
    )
    names = [row.country for row in countries]
    codes = dict(
        frappe.get_all("Country", filters={"name": ["in", names]}, fields=["name", "code"], as_list=True)
    )
    found = []
    for rule in rules:
        destinations = [
            codes[row.country].upper()
            for row in countries
            if row.parent == rule.name and codes.get(row.country)
        ]
        if destinations:
            found.append(
                {
                    "countries": destinations,
                    "currency": frappe.get_cached_value("Company", rule.company, "default_currency"),
                    "based_on": rule.calculate_based_on,
                    "amount": flt(rule.shipping_amount),
                    "conditions": [row for row in conditions if row.parent == rule.name],
                }
            )
    return found


def get_shipping_charge(rule: dict, amount: float):
    """The charge of an order of `amount`, as ERPNext Shipping Rule finds it. None: no charge row."""
    if rule["based_on"] == "Fixed":
        return rule["amount"]
    for row in rule["conditions"]:
        if not row.to_value or flt(row.from_value) <= amount <= flt(row.to_value):
            return flt(row.shipping_amount)
    return None


def get_listing(item_group: str) -> list:
    """The first page of the product listing of a category. With no products, its sub-categories."""
    query = get_ecommerce("ProductQuery")()
    query.build_item_group_filters(item_group)
    if query.settings.hide_variants:
        query.filters.append(["variant_of", "is", "not set"])
    rows = frappe.get_all(
        "Website Item",
        filters=query.filters,
        or_filters=query.or_filters,
        fields=["web_item_name as name", "route"],
        order_by="ranking desc",
        limit=query.page_length,
    )
    if not rows:
        rows = frappe.get_all(
            "Item Group",
            filters={"parent_item_group": item_group, "show_in_website": 1},
            fields=["name", "route"],
            order_by="weightage desc, name asc",
        )
    links = {row.route: row.name for row in rows if row.route}
    return make_links([(name, abs_url(route)) for route, name in links.items()])


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
    the public records that the fields link to: `products`, `slides`, `cards` and `posts`."""
    rows = (doc.get("page_blocks") if doc else None) or []
    pairs = [make_block(row) for row in rows if not row.get("hide_block")]
    products = get_products([name for _, links in pairs for name in links.get("Website Item", [])])
    for block, links in pairs:
        found = [products[name] for name in links.get("Website Item", []) if name in products]
        block["products"] = [dict(row, position=position) for position, row in enumerate(found, 1)]
        block["slides"] = [
            slide for name in links.get("Website Slideshow", []) for slide in get_slides(name)
        ]
        cards = [card for name in links.get("Homepage Section", []) for card in get_cards(name)]
        block["cards"] = [dict(card, position=position) for position, card in enumerate(cards, 1)]
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


def get_cards(name: str) -> list:
    """The cards of a Homepage Section. A section with custom HTML shows no cards."""
    if not frappe.db.exists("Homepage Section", name):
        return []
    section = frappe.get_cached_doc("Homepage Section", name)
    if section.section_based_on == "Custom HTML":
        return []
    return [
        {
            "title": plain_text(row.title),
            "description": plain_text(row.content),
            "url": abs_url(row.route),
            "image": get_public_url(row.image),
        }
        for row in section.section_cards
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
