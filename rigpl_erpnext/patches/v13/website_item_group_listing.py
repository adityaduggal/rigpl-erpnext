import frappe
from frappe.website.render import clear_cache

from rigpl_erpnext.website_rigpl.item_sync import (
    make_missing_web_items,
    sync_web_items,
    sync_web_search,
    sync_web_specs,
)


def execute():
    """
    Website Item settings and data after the v13 upgrade. Idempotent.
    - `sync_website_items`: the Item rules of `website_rigpl/item_sync.py` (#105, #106, #191).
      It runs here, after `convert_item_yes_no_to_check`, because the rules read `pl_item` as 0/1.
    - `index_website_items`: website and desk search by item code and name.
    - Category pages list templates, not variants, with ERPNext's own settings (#103):
    - E Commerce Settings Hide Variants on. Attribute Filters off, because ERPNext turns Hide
      Variants off while they are on, and a template has no attribute values. The filter
      rows stay, so they can be turned on again.
    - Include Descendants on each shown parent Item Group, so it lists the templates of its
      sub-categories and is not empty.
    """
    set_listing_settings()
    index_website_items()
    sync_website_items()
    clear_cache()


def sync_website_items():
    """ERPNext `v13_0.create_website_items` moves the Item Website Specification rows only for the
    Items it makes a Website Item for. This makes the missing Website Items of the PL Items and
    writes their image, publish state, warehouse, specifications and search rows from the Item.
    The rows left on non-PL Items are not used: a variant gets its rows when it becomes a PL Item."""
    made = make_missing_web_items()
    changed = sync_web_items()
    specs = sync_web_specs()
    search = sync_web_search()
    print(f"Website Items made: {made}, changed: {changed}, specifications: {specs}, search rows: {search}")


def index_website_items():
    """Desk search lists the doctypes of Global Search DocType rows. The `__global_search` rows of
    Item still have the v12 web routes; v13 Item has no web page, so they are not published."""
    if not frappe.db.exists("Global Search DocType", {"document_type": "Website Item"}):
        # Insert the row only: Global Search Settings.validate fails on the rows that rohit_common
        # keeps in the same child table for Rohit Settings.
        frappe.get_doc(
            {
                "doctype": "Global Search DocType",
                "name": frappe.generate_hash(length=10),
                "parent": "Global Search Settings",
                "parenttype": "Global Search Settings",
                "parentfield": "allowed_in_global_search",
                "idx": 1 + (frappe.db.count("Global Search DocType", {"parent": "Global Search Settings"})),
                "document_type": "Website Item",
            }
        ).db_insert()
        frappe.cache().hdel("global_search", "search_priorities")
        print("Global Search: Website Item is searchable in desk.")
    search = frappe.qb.Table("__global_search")
    frappe.qb.update(search).set(search.published, 0).where(
        (search.doctype == "Item") & (search.published == 1)
    ).run()


def set_listing_settings():
    settings = "E Commerce Settings"
    if not frappe.db.get_single_value(settings, "hide_variants"):
        frappe.db.set_single_value(settings, "hide_variants", 1)
        print("E Commerce Settings: Hide Variants is on.")
    if frappe.db.get_single_value(settings, "enable_attribute_filters"):
        frappe.db.set_single_value(settings, "enable_attribute_filters", 0)
        print("E Commerce Settings: Attribute Filters are off.")

    item_group = frappe.qb.DocType("Item Group")
    condition = (
        (item_group.show_in_website == 1) & (item_group.is_group == 1) & (item_group.include_descendants == 0)
    )
    count = len(frappe.qb.from_(item_group).select(item_group.name).where(condition).run())
    if count:
        frappe.qb.update(item_group).set(item_group.include_descendants, 1).where(condition).run()
        print(f"Item Groups: Include Descendants is on for {count} shown parent groups.")

    frappe.clear_cache(doctype=settings)
    frappe.clear_cache(doctype="Item Group")
