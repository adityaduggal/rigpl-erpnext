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
- `get_size_sort_keys` sorts items by size, in the order of the website variant table.

Only Item rows are used (`parenttype = 'Item'`). The same table also holds the rows of
Made to Order Item Attributes; `get_attribute_rows(..., parenttype=...)` reads those. The patch `add_item_variant_attribute_indexes` adds the
`(parent, attribute)` and `(attribute, attribute_value)` indexes these queries use.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

import frappe
from frappe.query_builder.functions import CustomFunction, Max
from frappe.utils import flt
from pypika.terms import Criterion, Term

CharLength = CustomFunction("CHAR_LENGTH", ["value"])

CHUNK_SIZE = 1000

# Filter fieldname: attribute. Quality is "<Base Material> Quality".
ATTRIBUTE_FILTERS = [
    ("rm", "Is RM"),
    ("bm", "Base Material"),
    ("tt", "Tool Type"),
    ("series", "Series"),
    ("spl", "Special Treatment"),
    ("purpose", "Purpose"),
    ("type", "Type Selector"),
    ("mtm", "Material to Machine"),
]

ROW_FIELDS = (
    "name",
    "idx",
    "attribute",
    "attribute_value",
    "prefix",
    "suffix",
    "use_in_description",
    "field_name",
    "from_range",
    "to_range",
    "increment",
    "numeric_values",
)


def attribute_filters(
    item_field: Term, values: Dict[str, Union[None, str, List[str]]]
) -> Criterion:
    """Return a criterion: `item_field` is an item that has each attribute value in `values`.
    A list value matches any of its values. An empty or None value is not a filter."""
    iva = frappe.qb.DocType("Item Variant Attribute")
    criteria = []
    for attribute, value in values.items():
        if not value:
            continue
        if isinstance(value, (list, tuple, set)):
            value_match = iva.attribute_value.isin(list(value))
        else:
            value_match = iva.attribute_value == value
        items = (
            frappe.qb.from_(iva)
            .select(iva.parent)
            .where(iva.attribute == attribute)
            .where(value_match)
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


def get_attribute_values(filters):
    """
    Returns {attribute: value} for the attribute filters
    """
    values = {attribute: filters.get(fieldname) for fieldname, attribute in ATTRIBUTE_FILTERS}
    values["%s Quality" % filters.get("bm")] = filters.get("quality")
    return values


def get_attribute_details(templates):
    """
    Returns the attributes of the templates in column order, each with its label details:
    [{name, numeric_values, max_length, name_in_template}]
    Column order: lowest idx in the templates, then the attribute used by more templates,
    then the name.
    """
    iva = frappe.qb.DocType("Item Variant Attribute")
    rows = []
    for chunk in chunks(templates):
        rows += (
            frappe.qb.from_(iva)
            .select(iva.parent, iva.attribute, iva.field_name, iva.idx)
            .where(iva.parent.isin(chunk) & (iva.parenttype == "Item"))
            .run(as_dict=True)
        )
    min_idx, used_by, field_names = {}, {}, {}
    for row in rows:
        min_idx[row.attribute] = min(row.idx, min_idx.get(row.attribute, row.idx))
        used_by.setdefault(row.attribute, set()).add(row.parent)
        field_names.setdefault(row.attribute, set()).add(row.field_name)
    attributes = sorted(min_idx, key=lambda a: (min_idx[a], -len(used_by[a]), a))

    meta = get_attribute_meta(attributes)
    att_details = []
    for att in attributes:
        att_meta = meta.get(att, frappe._dict(numeric_values=0, hidden=0, max_length=0))
        field_name = first_field_name(field_names[att])
        att_details.append(
            frappe._dict(
                name=att,
                numeric_values=att_meta.numeric_values,
                max_length=6 if att_meta.numeric_values else att_meta.max_length,
                name_in_template=get_name_in_template(att, att_meta, field_name),
            )
        )
    return att_details


def first_field_name(field_names):
    """
    Returns the field name the report used: no field name first, then the lowest, without case
    """
    if None in field_names:
        return None
    return sorted(field_names, key=lambda name: name.casefold())[0]


def get_name_in_template(att, att_meta, field_name):
    """
    Returns the column label: for a numeric or hidden attribute, the field name with the unit
    of the attribute name, for example "Dia (mm)" for d1_mm with field name "Dia (inch)"
    """
    if att_meta.numeric_values != 1:
        if att_meta.hidden == 1:
            return field_name.split("(", 1)[0] + "(" + att.split("_", 1)[1] + ")"
        return att
    n_row = att.split("_", 1)[1] if "_" in att else att
    if field_name and "(" in field_name:
        return field_name.split("(", 1)[0] + "(" + n_row + ")"
    return att


def get_template_attributes(template: str) -> List[dict]:
    """The template's Variant Attributes rows with Use in Description, in table order.

    `label` is the row's Field Name (for example d1_mm is "Flute Dia (mm)"). `numeric`
    comes from Item Attribute, because the values are stored as strings. `sort_attribute`
    is the attribute whose value sorts the column (see `pick_sort_attribute`).
    """
    iva = frappe.qb.DocType("Item Variant Attribute")
    item_attribute = frappe.qb.DocType("Item Attribute")
    rows = (
        frappe.qb.from_(iva)
        .left_join(item_attribute)
        .on(item_attribute.name == iva.attribute)
        .select(
            iva.attribute,
            iva.field_name,
            iva.use_in_description,
            item_attribute.numeric_values,
            item_attribute.source,
            item_attribute.update_from,
        )
        .where((iva.parent == template) & (iva.parenttype == "Item"))
        .orderby(iva.idx)
    ).run(as_dict=True)
    return [
        dict(
            {
                "attribute": row.attribute,
                "label": (row.field_name or "").strip() or row.attribute,
            },
            **pick_sort_attribute(row, rows),
        )
        for row in rows
        if row.use_in_description
    ]


def pick_sort_attribute(row: dict, template_rows: List[dict]) -> dict:
    """How a column sorts (#128). A text size such as d1_inch (1/8, 3/16) sorts by its numeric
    twin d1_mm: an attribute of the same template made from the same value in another UOM, so
    with the same `update_from` and source UOM. With no twin, a column sorts by its own value.
    """
    if not row.get("numeric_values") and row.get("source") == "UOM" and row.get("update_from"):
        for twin in template_rows:
            if (
                twin.get("numeric_values")
                and twin.get("source") == "UOM"
                and twin.get("update_from") == row["update_from"]
            ):
                return {"numeric": True, "sort_attribute": twin["attribute"]}
    return {"numeric": bool(row.get("numeric_values")), "sort_attribute": row["attribute"]}


def sort_key(value: str, numeric: bool) -> tuple:
    if not value:
        return (2, 0.0, "")
    if numeric:
        try:
            return (0, float(value), "")
        except ValueError:
            pass
    return (1, 0.0, value.lower())


def get_size_sort_keys(item_codes: Iterable[str]) -> Dict[str, tuple]:
    """Return {item_code: key} that sorts items by size, in the order of the website variant
    table (#222): by template, then by its attributes with Use in Description in table order.
    The item code is only the last tie-break, for items with the same size values.
    Queries: one per chunk for the templates and the values, and one per template.
    """
    items = list(dict.fromkeys(item_codes))
    templates: Dict[str, str] = {}
    for chunk in chunks(items):
        templates.update(
            frappe.get_all("Item", filters={"name": ("in", chunk)}, fields=["name", "variant_of"], as_list=True)
        )
    columns = {t: get_template_attributes(t) for t in sorted(set(templates.values())) if t}
    attributes = {c["sort_attribute"] for cols in columns.values() for c in cols}
    att_map = get_attribute_map(items, attributes) if attributes else {}
    keys = {}
    for item in items:
        template = templates.get(item) or ""
        values = att_map.get(item, {})
        size = tuple(sort_key(values.get(c["sort_attribute"]), c["numeric"]) for c in columns.get(template, []))
        keys[item] = (template, size, item)
    return keys
