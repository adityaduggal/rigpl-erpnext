"""
Item attribute values for reports and controllers (#131).

Reports used one `LEFT JOIN tabItem Variant Attribute` per attribute column: 9 to 24 self-joins
on a large table, and an SQL `CAST` sort that cannot use an index. Use these functions in place
of the joins:

- `attribute_filters` selects the items that have the given attribute values. Add it to the
  `where` of the item query.
- `get_attribute_map` gets the attribute values of these items in one query per chunk.
- `get_attribute_meta` gets the column details (numeric or not, longest value) in two queries.
- `attribute_sort_key` sorts the rows in Python, in the order MySQL used.

Only Item rows are used (`parenttype = 'Item'`). The same table also holds the rows of
Made to Order Item Attributes; `get_attribute_rows(..., parenttype=...)` reads those. The patch `add_item_variant_attribute_indexes` adds the
`(parent, attribute)` and `(attribute, attribute_value)` indexes these queries use.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import frappe
from frappe.query_builder.functions import CustomFunction, Max
from frappe.utils import flt
from pypika.terms import Criterion, Term

CharLength = CustomFunction("CHAR_LENGTH", ["value"])

CHUNK_SIZE = 1000
ROW_FIELDS = (
    "name",
    "idx",
    "attribute",
    "attribute_value",
    "prefix",
    "use_in_description",
    "field_name",
    "from_range",
    "to_range",
    "increment",
    "numeric_values",
)


def attribute_filters(item_field: Term, values: Dict[str, Optional[str]]) -> Criterion:
    """Return a criterion: `item_field` is an item that has each attribute value in `values`.
    An empty or None value is not a filter."""
    iva = frappe.qb.DocType("Item Variant Attribute")
    criteria = []
    for attribute, value in values.items():
        if not value:
            continue
        items = (
            frappe.qb.from_(iva)
            .select(iva.parent)
            .where(iva.attribute == attribute)
            .where(iva.attribute_value == value)
            .where(iva.parenttype == "Item")
        )
        criteria.append(item_field.isin(items))
    return Criterion.all(criteria)


def get_attribute_map(
    items: Iterable[str], attributes: Optional[Iterable[str]] = None
) -> Dict[str, Dict[str, str]]:
    """Return {item: {attribute: value}} for the given items. With `attributes`, return only these.
    An item with no attribute rows is not in the result."""
    attributes = list(attributes) if attributes is not None else None
    if attributes == []:
        return {}
    iva = frappe.qb.DocType("Item Variant Attribute")
    att_map: Dict[str, Dict[str, str]] = {}
    for chunk in chunks(items):
        query = (
            frappe.qb.from_(iva)
            .select(iva.parent, iva.attribute, iva.attribute_value)
            .where((iva.parent.isin(chunk)) & (iva.parenttype == "Item"))
        )
        if attributes:
            query = query.where(iva.attribute.isin(attributes))
        for parent, attribute, value in query.run():
            att_map.setdefault(parent, {})[attribute] = value
    return att_map


def get_attribute_rows(
    items: Iterable[str], parenttype: str = "Item"
) -> Dict[str, List[frappe._dict]]:
    """Return {parent: [attribute rows by idx]} with the fields of `ROW_FIELDS`. Use
    `parenttype="Made to Order Item Attributes"` to get the rows of those documents."""
    iva = frappe.qb.DocType("Item Variant Attribute")
    rows: Dict[str, List[frappe._dict]] = {}
    for chunk in chunks(items):
        query = (
            frappe.qb.from_(iva)
            .select(iva.parent, *[getattr(iva, field) for field in ROW_FIELDS])
            .where((iva.parent.isin(chunk)) & (iva.parenttype == parenttype))
            .orderby(iva.parent)
            .orderby(iva.idx)
        )
        for row in query.run(as_dict=True):
            rows.setdefault(row.pop("parent"), []).append(row)
    return rows


def get_attribute_meta(attributes: Iterable[str]) -> Dict[str, frappe._dict]:
    """Return {attribute: {numeric_values, hidden, max_length}} for report columns.
    `max_length` is the length of the longest Item Attribute Value, 0 for a numeric attribute.
    An attribute that is not an Item Attribute is not in the result."""
    attributes = list(attributes)
    if not attributes:
        return {}
    meta = {
        att.name: frappe._dict(numeric_values=att.numeric_values, hidden=att.hidden, max_length=0)
        for att in frappe.get_all(
            "Item Attribute",
            filters={"name": ("in", attributes)},
            fields=["name", "numeric_values", "hidden"],
        )
    }
    text_attributes = [name for name, att in meta.items() if not att.numeric_values]
    if text_attributes:
        iav = frappe.qb.DocType("Item Attribute Value")
        lengths = (
            frappe.qb.from_(iav)
            .select(iav.parent, Max(CharLength(iav.attribute_value)))
            .where(iav.parent.isin(text_attributes))
            .groupby(iav.parent)
            .run()
        )
        for attribute, max_length in lengths:
            meta[attribute].max_length = max_length or 0
    return meta


def attribute_sort_key(
    values: Dict[str, str], attributes: Sequence[str], numeric: Set[str]
) -> Tuple[Tuple, ...]:
    """Return a sort key for one item's `values`, in the order of `attributes`.
    It gives the order of an SQL `ORDER BY` on these columns: no value first, numeric attributes
    by number (like `CAST(... AS DECIMAL)`), text by case-insensitive value."""
    key = []
    for attribute in attributes:
        value = values.get(attribute)
        if value is None:
            key.append((0,))
        elif attribute in numeric:
            key.append((1, flt(value)))
        else:
            key.append((1, value.casefold()))
    return tuple(key)


def chunks(items: Iterable[str], size: int = CHUNK_SIZE):
    """Yield lists of at most `size` distinct items, so an `IN` list stays small."""
    unique = list(dict.fromkeys(items))
    for start in range(0, len(unique), size):
        yield unique[start : start + size]
