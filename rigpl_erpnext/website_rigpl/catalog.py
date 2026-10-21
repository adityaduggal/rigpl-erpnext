"""
Data for the website catalog pages. The website shows only what is published as a
Website Item: Website Item links to Item by `item_code` and to Item Group by `item_group`.
Only the attribute values come from the Item, because Website Item has none.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import frappe
from frappe.utils import cint, flt, fmt_money, nowdate

DEFAULT_STOCK_CAP = 100
DEFAULT_CAP_LABEL = "{cap}+"
DEFAULT_ZERO_LABEL = "On request"


def empty_table() -> dict:
    return {"common": [], "columns": [], "rows": [], "shop": no_shop()}


def no_shop() -> dict:
    return {"show_stock": False, "show_qty": False, "show_price": False, "show_cart": False}


def get_variant_table(website_item: str) -> dict:
    """The published variants of a template Website Item, for the RIGPL Variant Table block.

    The number of queries does not depend on the number of variants: the template Website
    Item, its attributes, the variant Website Items (`variant_of`), their attribute values,
    and for the shop columns their stock (Bin) and list price (Item Price).
    """
    if not isinstance(website_item, str) or not website_item:
        return empty_table()

    template = frappe.db.get_value(
        "Website Item",
        {"name": website_item, "published": 1, "has_variants": 1},
        ["item_code", "website_warehouse"],
        as_dict=True,
    )
    if not template:
        return empty_table()

    attributes = get_template_attributes(template.item_code)
    names = [a["attribute"] for a in attributes]
    variants = get_published_variants(template.item_code)
    values = get_attribute_values([v.item_code for v in variants], names)
    rows = pivot_variant_rows(variants, values, names)
    common, columns = split_columns(rows, attributes)
    shop, shop_rows = get_shop_info(template, variants)
    rows = add_shop_info(sort_variant_rows(rows, columns), shop_rows)
    return {"common": common, "columns": columns, "rows": rows, "shop": shop}


def get_template_attributes(template: str) -> List[dict]:
    """The template's Variant Attributes rows, in table order.

    `label` is the row's Field Name (for example d1_mm is "Flute Dia (mm)"). `numeric`
    comes from Item Attribute, because the values are stored as strings.
    """
    iva = frappe.qb.DocType("Item Variant Attribute")
    item_attribute = frappe.qb.DocType("Item Attribute")
    rows = (
        frappe.qb.from_(iva)
        .left_join(item_attribute)
        .on(item_attribute.name == iva.attribute)
        .select(iva.attribute, iva.field_name, item_attribute.numeric_values)
        .where((iva.parent == template) & (iva.parenttype == "Item") & (iva.use_in_description == 1))
        .orderby(iva.idx)
    ).run(as_dict=True)
    return [
        {
            "attribute": row.attribute,
            "label": (row.field_name or "").strip() or row.attribute,
            "numeric": bool(row.numeric_values),
        }
        for row in rows
    ]


def get_published_variants(template: str) -> list:
    """Disabling an Item unpublishes its Website Item, so `published` also hides disabled items."""
    web_item = frappe.qb.DocType("Website Item")
    return (
        frappe.qb.from_(web_item)
        .select(
            web_item.item_code,
            web_item.route,
            web_item.website_warehouse,
            web_item.on_backorder,
            web_item.stock_uom,
        )
        .where((web_item.variant_of == template) & (web_item.published == 1))
        .orderby(web_item.item_code)
    ).run(as_dict=True)


def get_attribute_values(item_codes: List[str], attributes: List[str]) -> list:
    if not item_codes or not attributes:
        return []

    iva = frappe.qb.DocType("Item Variant Attribute")
    return (
        frappe.qb.from_(iva)
        .select(iva.parent, iva.attribute, iva.attribute_value)
        .where(
            iva.parent.isin(item_codes)
            & (iva.parenttype == "Item")
            & iva.attribute.isin(attributes)
        )
    ).run(as_dict=True)


def pivot_variant_rows(variants: list, values: list, attributes: List[str]) -> List[dict]:
    """One row per variant, in the order of `variants`. A missing value is an empty string."""
    by_item: Dict[str, Dict[str, str]] = {}
    for value in values:
        by_item.setdefault(value["parent"], {})[value["attribute"]] = value["attribute_value"] or ""

    rows = []
    for variant in variants:
        found = by_item.get(variant["item_code"], {})
        rows.append(
            {
                "item_code": variant["item_code"],
                "route": variant.get("route") or "",
                "values": {attribute: found.get(attribute, "") for attribute in attributes},
            }
        )
    return rows


def split_columns(rows: List[dict], attributes: List[dict]) -> Tuple[List[Tuple[str, str]], List[dict]]:
    """Attributes with one value for all rows are common specs, shown once above the table
    as (label, value). The other attributes are the table columns. Both keep table order.
    """
    common = []
    columns = []
    if not rows:
        return common, columns

    for attribute in attributes:
        distinct = {row["values"][attribute["attribute"]] for row in rows}
        if len(distinct) == 1:
            value = distinct.pop()
            if value:
                common.append((attribute["label"], value))
        else:
            columns.append(attribute)
    return common, columns


def sort_variant_rows(rows: List[dict], columns: List[dict]) -> List[dict]:
    """Sort ascending by each column in table order, so d1_mm sorts before l1_mm.

    Numeric attributes compare as numbers ("10" after "9"). Empty values sort last.
    The sort is stable, so rows that tie keep their item code order.
    """

    def key(row):
        return tuple(sort_key(row["values"][c["attribute"]], c["numeric"]) for c in columns)

    return sorted(rows, key=key)


def sort_key(value: str, numeric: bool) -> tuple:
    if not value:
        return (2, 0.0, "")
    if numeric:
        try:
            return (0, float(value), "")
        except ValueError:
            pass
    return (1, 0.0, value.lower())


def get_shop_info(template: dict, variants: list) -> Tuple[dict, Dict[str, dict]]:
    """Stock, price and add-to-cart for each variant, as E Commerce Settings allow.

    Returns the column flags and
    {item_code: {"stock", "stock_value", "uom", "price", "price_value", "can_add"}}.
    Only the stock label and the capped sort value leave this function, so a quantity above
    the cap never reaches the page. Price and stock are in the stock UOM (#127 adds the sales UOM).
    """
    from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import (
        get_shopping_cart_settings,
    )

    cart = get_shopping_cart_settings()
    if not variants or not cart.enabled:
        return no_shop(), {}

    is_guest = frappe.session.user == "Guest"
    shop = {
        "show_stock": bool(cart.show_stock_availability),
        "show_qty": bool(cart.show_quantity_in_website),
        "show_price": bool(cart.show_price and not (is_guest and cart.hide_price_for_guest)),
        "show_cart": True,
    }

    item_codes = [v.item_code for v in variants]
    warehouses = {v.item_code: v.website_warehouse or template.website_warehouse for v in variants}
    stock = get_stock_qty(warehouses)
    prices = {}
    if shop["show_price"]:
        prices = get_list_prices(item_codes, template.item_code, get_selling_price_list(cart))

    settings = frappe.get_cached_doc("RIGPL Settings")
    cap = cint(settings.get("website_stock_cap")) or DEFAULT_STOCK_CAP
    cap_label = settings.get("website_stock_cap_label") or DEFAULT_CAP_LABEL
    zero_label = settings.get("website_zero_stock_label") or DEFAULT_ZERO_LABEL

    shop_rows = {}
    for variant in variants:
        qty = stock.get(variant.item_code, 0.0)
        price = prices.get(variant.item_code) or prices.get(template.item_code)
        in_stock = qty > 0 or variant.on_backorder or cart.allow_items_not_in_stock
        shop_rows[variant.item_code] = {
            "stock": cap_stock(qty, cap, cap_label, zero_label, shop["show_qty"]),
            "stock_value": stock_sort_value(qty, cap, shop["show_qty"]),
            "uom": variant.stock_uom or "",
            "price": fmt_money(price.price_list_rate, currency=price.currency) if price else "",
            "price_value": flt(price.price_list_rate) if price else "",
            "can_add": bool(price and in_stock),
        }
    return shop, shop_rows


def add_shop_info(rows: List[dict], shop_rows: Dict[str, dict]) -> List[dict]:
    """New rows with a `shop` dict. A row with no shop info gets empty values."""
    empty = {"stock": "", "stock_value": "", "uom": "", "price": "", "price_value": "", "can_add": False}
    return [dict(row, shop=shop_rows.get(row["item_code"], empty)) for row in rows]


def get_stock_qty(warehouses: Dict[str, Optional[str]]) -> Dict[str, float]:
    """Free quantity of each item in its website warehouse, as ERPNext counts it:
    actual minus the reserved quantities. One query on the Bin (item_code, warehouse) index.
    """
    pairs = {(code, wh) for code, wh in warehouses.items() if wh}
    if not pairs:
        return {}

    bin_ = frappe.qb.DocType("Bin")
    rows = (
        frappe.qb.from_(bin_)
        .select(
            bin_.item_code,
            bin_.warehouse,
            (
                bin_.actual_qty
                - bin_.reserved_qty
                - bin_.reserved_qty_for_production
                - bin_.reserved_qty_for_sub_contract
            ).as_("free_qty"),
        )
        .where(
            bin_.item_code.isin([code for code, _ in pairs])
            & bin_.warehouse.isin(list({wh for _, wh in pairs}))
        )
    ).run(as_dict=True)
    return {
        row.item_code: max(flt(row.free_qty), 0.0) for row in rows if (row.item_code, row.warehouse) in pairs
    }


def cap_stock(qty: float, cap: int, cap_label: str, zero_label: str, show_qty: bool = True) -> str:
    """The stock text for the website. Above the cap it is the label (for example 100+),
    so the real quantity stays private.
    """
    if qty <= 0:
        return zero_label
    if not show_qty:
        return "In stock"
    if qty > cap:
        return cap_label.replace("{cap}", str(cap))
    return "{:g}".format(qty)


def stock_sort_value(qty: float, cap: int, show_qty: bool = True) -> float:
    """The number the page sorts the stock by. It is never above the cap, so the page
    source does not show the real quantity either.
    """
    if qty <= 0:
        return 0
    if not show_qty:
        return 1
    return min(qty, cap)


def get_selling_price_list(cart) -> Optional[str]:
    """The customer's default price list for a logged-in user, else the E Commerce price list.

    Read only: ERPNext `get_party` inserts a Customer for a user that has none, which a
    page view must not do.
    """
    if frappe.session.user != "Guest":
        from frappe.contacts.doctype.contact.contact import get_contact_name

        contact = get_contact_name(frappe.session.user)
        customer = contact and frappe.db.get_value(
            "Dynamic Link",
            {"parenttype": "Contact", "parent": contact, "link_doctype": "Customer"},
            "link_name",
        )
        if customer:
            price_list, group = frappe.db.get_value(
                "Customer", customer, ["default_price_list", "customer_group"]
            ) or (None, None)
            price_list = price_list or frappe.db.get_value("Customer Group", group, "default_price_list")
            if price_list:
                return price_list
    return cart.price_list


def get_list_prices(item_codes: List[str], template: str, price_list: Optional[str]) -> Dict[str, dict]:
    """Selling Item Price of the variants and the template in one query. Pricing rules are
    not applied (#77). A price for one customer only, or out of its valid dates, is skipped.
    """
    if not price_list or not item_codes:
        return {}

    today = nowdate()
    item_price = frappe.qb.DocType("Item Price")
    rows = (
        frappe.qb.from_(item_price)
        .select(item_price.item_code, item_price.price_list_rate, item_price.currency)
        .where(
            (item_price.price_list == price_list)
            & item_price.item_code.isin(item_codes + [template])
            & (item_price.customer.isnull() | (item_price.customer == ""))
            & (item_price.valid_from.isnull() | (item_price.valid_from <= today))
            & (item_price.valid_upto.isnull() | (item_price.valid_upto >= today))
        )
        .orderby(item_price.valid_from, order=frappe.qb.desc)
    ).run(as_dict=True)

    prices = {}
    for row in rows:
        prices.setdefault(row.item_code, row)  # the latest valid_from wins
    return prices
