"""
Revenue rank for the website (#101). The products that make the most revenue show first.

- A product is a Website Item with no `variant_of`: a template, or an item without variants.
  Its revenue is the `base_net_amount` of the submitted Sales Invoice Items of its variants
  (or of itself) in the last N months. Credit notes have negative amounts, so they reduce it.
  N is the shortest period in RIGPL Settings `rol_calculation`.
- Website Item `ranking` is the position: the product with the most revenue gets the highest
  number. ERPNext lists the products of a category by `ranking desc`. Usage (consumption in
  Stock Entries) only breaks ties, for example between products with no sales.
- Item Group `weightage` is the revenue of the products in the group and its descendants,
  divided by a power of 10 and rounded, so it is a whole number from 1 to 1000 (0 for no
  revenue). The divisor is the smallest power of 10 that makes the largest group 1000 or less,
  so weightage x divisor is about the revenue.

Both are standard fields. The quarterly job writes only the values that change, so it replaces
a value set by hand.
"""
from __future__ import annotations

from math import ceil, log10
from typing import Dict, List, Tuple

import frappe
from frappe.query_builder.functions import Coalesce, Sum
from frappe.utils import add_months, flt, nowdate
from rohit_common.utils.background_doc_processing import enqueue_once

DEFAULT_MONTHS = 12
MAX_WEIGHTAGE = 1000
CONSUMPTION_PURPOSES = ("Material Issue", "Repack", "Manufacture", "Material Consumption for Manufacture")


def enqueue_sales_rank():
    enqueue_once("rigpl_erpnext.website_rigpl.sales_rank.update_sales_rank", queue="long", timeout=3600)


def update_sales_rank() -> Tuple[int, int]:
    """Write the changed Website Item `ranking` and Item Group `weightage`.
    Return the number of Website Items and Item Groups changed."""
    from_date = add_months(nowdate(), -get_rank_months())
    revenue = get_product_revenue(from_date)
    usage = get_product_usage(from_date)

    products = frappe.get_all(
        "Website Item",
        filters={"variant_of": ("is", "not set")},
        fields=["name", "item_code", "item_group", "ranking"],
    )
    rankings = rank_products([p.item_code for p in products], revenue, usage)
    items_changed = 0
    for product in products:
        ranking = rankings[product.item_code]
        if product.ranking != ranking:
            frappe.db.set_value("Website Item", product.name, "ranking", ranking, update_modified=False)
            items_changed += 1

    group_revenue: Dict[str, float] = {}
    for product in products:
        if product.item_group:
            group_revenue[product.item_group] = group_revenue.get(product.item_group, 0) + revenue.get(
                product.item_code, 0
            )
    groups = frappe.get_all("Item Group", fields=["name", "lft", "rgt", "weightage"])
    totals = sum_group_revenue(group_revenue, groups)
    weightages, divisor = scale_weightage(totals)
    groups_changed = 0
    for group in groups:
        if group.weightage != weightages[group.name]:
            frappe.db.set_value("Item Group", group.name, "weightage", weightages[group.name], update_modified=False)
            groups_changed += 1

    if items_changed or groups_changed:
        from frappe.website.render import clear_cache

        clear_cache()
    print(
        f"Sales rank: {items_changed} Website Items and {groups_changed} Item Groups changed. "
        f"Item Group weightage = revenue / {divisor}."
    )
    return items_changed, groups_changed


def get_rank_months() -> int:
    """The shortest period of RIGPL Settings `rol_calculation`, for example 12 of "12,15,18"."""
    value = frappe.db.get_single_value("RIGPL Settings", "rol_calculation") or ""
    months = [int(part) for part in value.split(",") if part.strip().isdigit()]
    return min(months) if months else DEFAULT_MONTHS


def get_product_revenue(from_date: str) -> Dict[str, float]:
    """{product item code: revenue} in one query. A variant counts for its template."""
    sii = frappe.qb.DocType("Sales Invoice Item")
    si = frappe.qb.DocType("Sales Invoice")
    item = frappe.qb.DocType("Item")
    product = Coalesce(item.variant_of, item.name)
    rows = (
        frappe.qb.from_(sii)
        .inner_join(si)
        .on(si.name == sii.parent)
        .inner_join(item)
        .on(item.name == sii.item_code)
        .select(product.as_("product"), Sum(sii.base_net_amount).as_("revenue"))
        .where((si.docstatus == 1) & (si.posting_date >= from_date))
        .groupby(product)
    ).run(as_dict=True)
    return {row.product: flt(row.revenue) for row in rows}


def get_product_usage(from_date: str) -> Dict[str, float]:
    """{product item code: consumed stock qty} in one query: the rows with a source warehouse
    of submitted Stock Entries that consume stock."""
    sed = frappe.qb.DocType("Stock Entry Detail")
    se = frappe.qb.DocType("Stock Entry")
    item = frappe.qb.DocType("Item")
    product = Coalesce(item.variant_of, item.name)
    rows = (
        frappe.qb.from_(sed)
        .inner_join(se)
        .on(se.name == sed.parent)
        .inner_join(item)
        .on(item.name == sed.item_code)
        .select(product.as_("product"), Sum(sed.transfer_qty).as_("usage"))
        .where(
            (se.docstatus == 1)
            & (se.posting_date >= from_date)
            & se.purpose.isin(CONSUMPTION_PURPOSES)
            & sed.s_warehouse.notnull()
            & (sed.s_warehouse != "")
        )
        .groupby(product)
    ).run(as_dict=True)
    return {row.product: flt(row.usage) for row in rows}


def rank_products(names: List[str], revenue: Dict[str, float], usage: Dict[str, float]) -> Dict[str, int]:
    """{name: rank}. Sorted by revenue, then usage, then name. The first gets `len(names)`,
    the last gets 1, so a higher rank shows first. Used for products and for groups."""
    ordered = sorted(names, key=lambda name: (-revenue.get(name, 0), -usage.get(name, 0), name))
    count = len(ordered)
    return {name: count - position for position, name in enumerate(ordered)}


def scale_weightage(totals: Dict[str, float], top_value: int = MAX_WEIGHTAGE) -> Tuple[Dict[str, int], int]:
    """({group: weightage}, divisor). Revenue / divisor, rounded, from 1 to `top_value`.
    A group with no revenue (or a negative one) gets 0."""
    top = max(totals.values(), default=0)
    divisor = 10 ** max(0, ceil(log10(top / top_value))) if top > 0 else 1
    weightages = {}
    for name, total in totals.items():
        weightages[name] = min(top_value, max(1, round(total / divisor))) if total > 0 else 0
    return weightages, divisor


def sum_group_revenue(group_revenue: Dict[str, float], groups: List[dict]) -> Dict[str, float]:
    """{group: revenue of the group and its descendants}, from the nested set `lft` / `rgt`."""
    bounds = {g["name"]: (g["lft"], g["rgt"]) for g in groups}
    totals = {}
    for group in groups:
        total = 0.0
        for name, value in group_revenue.items():
            if name in bounds and group["lft"] <= bounds[name][0] and bounds[name][1] <= group["rgt"]:
                total += value
        totals[group["name"]] = flt(total, 2)
    return totals
