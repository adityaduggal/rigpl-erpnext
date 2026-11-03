"""
Item is the controller of its Website Item (#105).

- `website_image` and `thumbnail` are the Item `image`.
- The Website Item is published if and only if the Item is enabled and `pl_item` is set.
  An enabled `pl_item` Item with no Website Item gets one (#106). An unpublished Website Item
  is not deleted, so its route and redirects stay.
- `web_long_description` is the text that `generate_description` makes for a variant. A
  template has no generated text, so its Website Item keeps the text an editor gives it.
- `website_warehouse` is the Item Default warehouse, if the Item has one.
- The `website_specifications` of a PL variant come from the template attributes with
  `use_in_description` (#191). v13 Item has no such table.
- Each Website Item has a `__global_search` row (website `/search` and desk search) with its
  `SEARCH_FIELDS`. The writes here skip the save hooks, so `sync_web_search` writes the row.
  The patch `website_item_group_listing` makes `__global_search` InnoDB, so 3-character words
  (T42, HSS) are in its full-text index.

The Item `on_update` hook applies the rules to one Item. The daily job `variant_copy`
applies them to all Items.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import frappe
from frappe.query_builder.functions import Count
from frappe.utils import cint, now
from frappe.utils.global_search import get_formatted_value, insert_values_for_multiple_docs
from frappe.website.render import clear_cache

from ..utils.batch_write_utils import bulk_insert_rows, clear_document_cache
from ..utils.item_attribute_utils import chunks, get_attribute_map
from .compat import get_ecommerce

# Property Setters in custom/website_item.json give these fields `in_global_search`.
SEARCH_FIELDS = ("web_item_name", "item_code")
SPEC_FIELDS = (
    "name", "creation", "modified", "owner", "modified_by", "docstatus", "parent", "parentfield",
    "parenttype", "idx", "label", "description",
)


def plan_web_item_changes(rows: List[dict]) -> Dict[str, dict]:
    """Return {website item name: {field: new value}} for the fields that are wrong.

    Each row is a Website Item with the `image`, `disabled`, `pl_item` and `default_warehouse`
    of its Item.
    """
    changes = {}
    for row in rows:
        changed = {}
        image = row.get("image") or None
        for field in ("website_image", "thumbnail"):
            if (row.get(field) or None) != image:
                changed[field] = image
        warehouse = row.get("default_warehouse")
        if warehouse and row.get("website_warehouse") != warehouse:
            changed["website_warehouse"] = warehouse
        published = int(not cint(row.get("disabled")) and cint(row.get("pl_item")))
        if cint(row.get("published")) != published:
            changed["published"] = published
        if changed:
            changes[row["name"]] = changed
    return changes


def sync_web_items(item_codes: Optional[List[str]] = None) -> int:
    """Apply the Item rules to the Website Items of `item_codes`, or of all Items if None.
    Return the number of Website Items changed."""
    if item_codes is not None and not item_codes:
        return 0

    web_item = frappe.qb.DocType("Website Item")
    item = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(web_item)
        .inner_join(item)
        .on(item.name == web_item.item_code)
        .select(
            web_item.name,
            web_item.published,
            web_item.website_image,
            web_item.thumbnail,
            web_item.website_warehouse,
            web_item.item_code,
            item.image,
            item.disabled,
            item.pl_item,
        )
    )
    if item_codes is not None:
        query = query.where(web_item.item_code.isin(item_codes))

    rows = query.run(as_dict=True)
    warehouses = get_default_warehouses([row.item_code for row in rows])
    for row in rows:
        row["default_warehouse"] = warehouses.get(row.item_code)
    # set_value, not save: WebsiteItem.make_thumbnail would replace the thumbnail rule.
    changes = plan_web_item_changes(rows)
    for name, changed in changes.items():
        frappe.db.set_value("Website Item", name, changed)
    if changes:
        clear_cache()
    return len(changes)


def get_default_warehouses(item_codes: Iterable[str]) -> Dict[str, str]:
    """Return {item code: Item Default warehouse} for the items that have one."""
    item_default = frappe.qb.DocType("Item Default")
    warehouses = {}
    for chunk in chunks(item_codes):
        rows = (
            frappe.qb.from_(item_default)
            .select(item_default.parent, item_default.default_warehouse)
            .where(item_default.parent.isin(chunk))
            .where(item_default.parenttype == "Item")
            .where(item_default.default_warehouse.isnotnull())
            .orderby(item_default.idx)
        ).run()
        warehouses.update({parent: warehouse for parent, warehouse in rows if warehouse})
    return warehouses


def make_missing_web_items(item_codes: Optional[List[str]] = None) -> int:
    """Make a Website Item with ERPNext `make_website_item` for each enabled `pl_item` Item
    of `item_codes` (or all Items if None) that has none (#106). Return the number made.
    `sync_web_items` then sets its image and publish state.
    """
    make_website_item = get_ecommerce("make_website_item")

    if item_codes is not None and not item_codes:
        return 0

    item = frappe.qb.DocType("Item")
    web_item = frappe.qb.DocType("Website Item")
    query = (
        frappe.qb.from_(item)
        .left_join(web_item)
        .on(web_item.item_code == item.name)
        .select(item.name)
        .where((item.disabled == 0) & (item.pl_item == 1) & web_item.name.isnull())
        .orderby(item.has_variants, order=frappe.qb.desc)  # a template before its variants
    )
    if item_codes is not None:
        query = query.where(item.name.isin(item_codes))

    made = 0
    for (item_code,) in query.run():
        # a variant's Website Item can make its template's one (WebsiteItem.update_template_item)
        if not frappe.db.exists("Website Item", {"item_code": item_code}):
            make_website_item(frappe.get_doc("Item", item_code))
            made += 1
    return made


def set_web_long_description(item_code: str, long_desc: str) -> bool:
    """Write `long_desc` to the Website Item of `item_code` if it is different.
    Return True if it wrote."""
    web_item = frappe.db.get_value(
        "Website Item", {"item_code": item_code}, ["name", "web_long_description"], as_dict=True
    )
    if not web_item or (web_item.web_long_description or "") == (long_desc or ""):
        return False
    frappe.db.set_value("Website Item", web_item.name, "web_long_description", long_desc)
    return True


def on_item_update(doc, method=None):
    """Item on_update. Item validate puts the generated long description, and the variants
    of a disabled template that are still PL Items, in the flags."""
    variants = doc.flags.variants_to_unlist
    if variants:
        unlist_variants(variants)
    make_missing_web_items([doc.name])
    changed = sync_web_items([doc.name])
    if doc.variant_of and sync_web_specs([doc.name]) and not changed:
        clear_cache()
    long_desc = doc.flags.web_long_description
    if doc.variant_of and long_desc and set_web_long_description(doc.name, long_desc):
        clear_cache()
    sync_web_search([doc.name])


def build_web_specs(item_codes: Iterable[str]) -> Dict[str, List[Tuple[str, str]]]:
    """Return {variant: [(label, description)]} for the enabled PL variants in `item_codes`.

    There is one row for each template attribute with `use_in_description`, in template order.
    The label is the template `field_name`. The description is the variant value for a numeric
    attribute, else the `long_description` of the attribute value without its quotes. As in
    v12, a row can have an empty description (Special Treatment "None" has `""`).
    """
    item = frappe.qb.DocType("Item")
    variants = {}
    for chunk in chunks(item_codes):
        variants.update(
            frappe.qb.from_(item)
            .select(item.name, item.variant_of)
            .where(item.name.isin(chunk))
            .where((item.pl_item == 1) & (item.disabled == 0) & (item.has_variants == 0))
            .where(item.variant_of.isnotnull())
            .run()
        )
    if not variants:
        return {}
    template_rows = get_description_attributes(variants.values())
    values = get_attribute_map(variants)
    long_descriptions = get_long_descriptions(
        (row.attribute, values.get(variant, {}).get(row.attribute))
        for variant, template in variants.items()
        for row in template_rows.get(template, [])
        if not cint(row.numeric_values)
    )
    specs = {}
    for variant, template in variants.items():
        specs[variant] = []
        for row in template_rows.get(template, []):
            value = values.get(variant, {}).get(row.attribute)
            if value is None:
                continue
            if not cint(row.numeric_values):
                value = long_descriptions.get((row.attribute, value), value)
            specs[variant].append((row.field_name, value))
    return specs


def get_description_attributes(templates: Iterable[str]) -> Dict[str, List[frappe._dict]]:
    """Return {template: its attribute rows with `use_in_description`, in idx order}."""
    iva = frappe.qb.DocType("Item Variant Attribute")
    attribute = frappe.qb.DocType("Item Attribute")
    rows_by_template = {}
    for chunk in chunks(templates):
        rows = (
            frappe.qb.from_(iva)
            .inner_join(attribute)
            .on(attribute.name == iva.attribute)
            .select(iva.parent, iva.attribute, iva.field_name, attribute.numeric_values)
            .where(iva.parent.isin(chunk))
            .where((iva.parenttype == "Item") & (iva.use_in_description == 1))
            .orderby(iva.parent)
            .orderby(iva.idx)
        ).run(as_dict=True)
        for row in rows:
            rows_by_template.setdefault(row.parent, []).append(row)
    return rows_by_template


def get_long_descriptions(pairs: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], str]:
    """Return {(attribute, value): long description without its quotes}."""
    pairs = {pair for pair in pairs if pair[1] is not None}
    iav = frappe.qb.DocType("Item Attribute Value")
    long_descriptions = {}
    for chunk in chunks(sorted({value for _, value in pairs})):
        rows = (
            frappe.qb.from_(iav)
            .select(iav.parent, iav.attribute_value, iav.long_description)
            .where(iav.parent.isin(sorted({attribute for attribute, _ in pairs})))
            .where(iav.attribute_value.isin(chunk))
        ).run()
        for parent, value, long_description in rows:
            if (parent, value) in pairs and long_description is not None:
                long_descriptions[(parent, value)] = strip_quotes(long_description)
    return long_descriptions


def strip_quotes(text: str) -> str:
    """Item Attribute Value keeps the long description in double quotes: "Solid Carbide"."""
    if len(text) > 1 and text[0] == text[-1] == '"':
        return text[1:-1]
    return text


def sync_web_specs(item_codes: Optional[List[str]] = None) -> int:
    """Write the `website_specifications` of the Website Items of the PL variants in `item_codes`
    (or all PL variants if None) where they are different. Return the number changed."""
    if item_codes is None:
        item_codes = frappe.get_all(
            "Item",
            filters={"pl_item": 1, "disabled": 0, "has_variants": 0, "variant_of": ["is", "set"]},
            pluck="name",
        )
    specs = build_web_specs(item_codes)
    web_items = get_web_item_names(specs)
    current = get_current_specs(web_items.values())
    changed = {
        web_items[code]: rows for code, rows in specs.items()
        if code in web_items and current.get(web_items[code], []) != rows
    }
    if not changed:
        return 0
    spec = frappe.qb.DocType("Item Website Specification")
    for chunk in chunks(changed):
        frappe.qb.from_(spec).delete().where(spec.parent.isin(chunk)).where(
            spec.parenttype == "Website Item"
        ).run()
    timestamp, user = now(), frappe.session.user
    bulk_insert_rows("Item Website Specification", SPEC_FIELDS, [
        (frappe.generate_hash(length=10), timestamp, timestamp, user, user, 0, web_item,
            "website_specifications", "Website Item", idx, label, description)
        for web_item, rows in changed.items()
        for idx, (label, description) in enumerate(rows, start=1)
    ])
    clear_document_cache("Website Item", changed)
    return len(changed)


def get_web_item_names(item_codes: Iterable[str]) -> Dict[str, str]:
    """Return {item code: Website Item name}."""
    web_items = {}
    for chunk in chunks(item_codes):
        web_items.update(
            frappe.get_all(
                "Website Item",
                filters={"item_code": ["in", chunk]},
                fields=["item_code", "name"],
                as_list=True,
            )
        )
    return web_items


def get_current_specs(web_items: Iterable[str]) -> Dict[str, List[Tuple[str, str]]]:
    """Return {Website Item: [(label, description)] in idx order}."""
    spec = frappe.qb.DocType("Item Website Specification")
    current = {}
    for chunk in chunks(web_items):
        rows = (
            frappe.qb.from_(spec)
            .select(spec.parent, spec.label, spec.description)
            .where(spec.parent.isin(chunk))
            .where(spec.parenttype == "Website Item")
            .orderby(spec.parent)
            .orderby(spec.idx)
        ).run()
        for parent, label, description in rows:
            current.setdefault(parent, []).append((label, description))
    return current


def build_search_rows(web_items: List[dict]) -> Dict[str, dict]:
    """Return {Website Item: __global_search row} as frappe `update_global_search` makes it."""
    meta = frappe.get_meta("Website Item")
    fields = sorted(
        (meta.get_field(fieldname) for fieldname in SEARCH_FIELDS),
        key=lambda field: field.idx,
    )
    rows = {}
    for web_item in web_items:
        content = [get_formatted_value(web_item[f.fieldname], f) for f in fields if web_item.get(f.fieldname)]
        rows[web_item["name"]] = {
            "content": " ||| ".join(content),
            "published": 1 if cint(web_item.get("published")) else 0,
            "title": (web_item.get("web_item_name") or "")[: int(frappe.db.VARCHAR_LEN)],
            "route": web_item.get("route") or "",
        }
    return rows


def sync_web_search(item_codes: Optional[List[str]] = None) -> int:
    """Write the `__global_search` rows of the Website Items of `item_codes` (or of all) that are
    different. Return the number written."""
    if item_codes is not None and not item_codes:
        return 0
    web_item = frappe.qb.DocType("Website Item")
    query = frappe.qb.from_(web_item).select(
        web_item.name, web_item.published, web_item.route, *[web_item[f] for f in SEARCH_FIELDS]
    )
    if item_codes is not None:
        query = query.where(web_item.item_code.isin(item_codes))
    wanted = build_search_rows(query.run(as_dict=True))
    current = get_search_rows(wanted)
    changed = [name for name, row in wanted.items() if current.get(name) != row]
    if not changed:
        return 0
    search = frappe.qb.Table("__global_search")
    for chunk in chunks(changed):
        frappe.qb.from_(search).delete().where(
            (search.doctype == "Website Item") & search.name.isin(chunk)
        ).run()
    insert_values_for_multiple_docs([
        {
            "doctype": frappe.db.escape("Website Item"),
            "name": frappe.db.escape(name),
            "content": frappe.db.escape(wanted[name]["content"]),
            "published": wanted[name]["published"],
            "title": frappe.db.escape(wanted[name]["title"]),
            "route": frappe.db.escape(wanted[name]["route"]),
        }
        for name in changed
    ])
    return len(changed)


def get_search_rows(web_items: Iterable[str]) -> Dict[str, dict]:
    """Return {Website Item: its __global_search row}."""
    search = frappe.qb.Table("__global_search")
    rows = {}
    for chunk in chunks(web_items):
        result = (
            frappe.qb.from_(search)
            .select(search.name, search.content, search.published, search.title, search.route)
            .where((search.doctype == "Website Item") & search.name.isin(chunk))
        ).run(as_dict=True)
        for row in result:
            rows[row.name] = {
                "content": row.content or "",
                "published": cint(row.published),
                "title": row.title or "",
                "route": row.route or "",
            }
    return rows


def unlist_variants(item_codes: List[str]) -> None:
    """Turn off PL Item on `item_codes` and unpublish their Website Items (#107)."""
    item = frappe.qb.DocType("Item")
    frappe.qb.update(item).set(item.pl_item, 0).where(item.name.isin(item_codes)).run()
    sync_web_items(item_codes)
    sync_web_search(item_codes)
    frappe.msgprint(f"PL Item is turned off on {len(item_codes)} variants of this template.")


def get_pl_item_mismatches() -> List[dict]:
    """Templates that are not PL Items but have variants that are (#107), with the count."""
    template = frappe.qb.DocType("Item")
    variant = frappe.qb.DocType("Item").as_("variant")
    return (
        frappe.qb.from_(template)
        .inner_join(variant)
        .on(variant.variant_of == template.name)
        .select(template.name, Count(variant.name).as_("variants"))
        .where((template.pl_item == 0) & (variant.pl_item == 1))
        .groupby(template.name)
    ).run(as_dict=True)
