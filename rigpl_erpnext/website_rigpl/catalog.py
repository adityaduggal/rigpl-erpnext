"""
Data for the website catalog pages. The website shows only what is published as a
Website Item: Website Item links to Item by `item_code` and to Item Group by `item_group`.
Only the attribute values come from the Item, because Website Item has none.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import frappe


def empty_table() -> dict:
    return {"common": [], "columns": [], "rows": []}


def get_variant_table(website_item: str) -> dict:
    """The published variants of a template Website Item, for the RIGPL Variant Table block.

    Four indexed queries, whatever the number of variants: the template Website Item,
    its attributes, the variant Website Items (`variant_of`) and their attribute values.
    """
    if not isinstance(website_item, str) or not website_item:
        return empty_table()

    template = frappe.db.get_value(
        "Website Item", {"name": website_item, "published": 1, "has_variants": 1}, "item_code"
    )
    if not template:
        return empty_table()

    attributes = get_template_attributes(template)
    names = [a["attribute"] for a in attributes]
    variants = get_published_variants(template)
    values = get_attribute_values([v.item_code for v in variants], names)
    rows = pivot_variant_rows(variants, values, names)
    common, columns = split_columns(rows, attributes)
    return {"common": common, "columns": columns, "rows": sort_variant_rows(rows, columns)}


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
        .select(web_item.item_code, web_item.route)
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
