"""
Item is the controller of its Website Item (#105).

- `website_image` and `thumbnail` are the Item `image`.
- The Website Item is published if and only if the Item is enabled and `pl_item = "Yes"`.
  An unpublished Website Item is not deleted, so its route and redirects stay.
- `web_long_description` is the text that `generate_description` makes for a variant. A
  template has no generated text, so its Website Item keeps the text an editor gives it.

The Item `on_update` hook applies the rules to one Item. The daily job `variant_copy`
applies them to all Items.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import frappe
from frappe.utils import cint
from frappe.website.render import clear_cache


def plan_web_item_changes(rows: List[dict]) -> Dict[str, dict]:
    """Return {website item name: {field: new value}} for the fields that are wrong.

    Each row is a Website Item with the `image`, `disabled` and `pl_item` of its Item.
    """
    changes = {}
    for row in rows:
        changed = {}
        image = row.get("image") or None
        for field in ("website_image", "thumbnail"):
            if (row.get(field) or None) != image:
                changed[field] = image
        published = int(not cint(row.get("disabled")) and row.get("pl_item") == "Yes")
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
            item.image,
            item.disabled,
            item.pl_item,
        )
    )
    if item_codes is not None:
        query = query.where(web_item.item_code.isin(item_codes))

    # set_value, not save: WebsiteItem.make_thumbnail would replace the thumbnail rule.
    changes = plan_web_item_changes(query.run(as_dict=True))
    for name, changed in changes.items():
        frappe.db.set_value("Website Item", name, changed)
    if changes:
        clear_cache()
    return len(changes)


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
    """Item on_update. Item validate puts the generated long description in the flags."""
    sync_web_items([doc.name])
    long_desc = doc.flags.web_long_description
    if doc.variant_of and long_desc and set_web_long_description(doc.name, long_desc):
        clear_cache()
