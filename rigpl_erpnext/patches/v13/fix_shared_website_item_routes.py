import frappe
from frappe.query_builder.functions import Coalesce
from frappe.website.render import clear_cache

from rigpl_erpnext.website_rigpl.item_sync import sync_web_items
from rigpl_erpnext.website_rigpl.route_sync import add_redirects
from rigpl_erpnext.website_rigpl.routes import plan_shared_route_fixes

# Web fields that v13 Item does not have. Their v12 values are still in the Item table.
V12_WEB_FIELDS = ("web_long_description", "website_image_alt", "slideshow", "website_content")


def execute():
    """
    Repair the Website Items that the v13 migration made. Idempotent: a second run changes
    nothing.
    - #99: after the migration, 2,493 Website Items shared 133 routes, so 20 template pages
      showed a variant. Give each Website Item a route of its own.
    - #105: ERPNext made a template Website Item without its web fields when a variant came
      before its template. Copy the web fields from Item, and apply the Item rules
      (`website_rigpl/item_sync.py`).
    """
    fix_shared_routes()
    publish_templates_of_published_variants()
    move_item_website_item_groups()
    fill_empty_web_fields_from_item()
    print(f"Website Items changed as per Item: {sync_web_items()}.")
    clear_cache()


def fix_shared_routes():
    web_items = frappe.get_all(
        "Website Item", fields=["name", "item_code", "route", "has_variants", "variant_of"]
    )
    templates = [row.item_code for row in web_items if row.has_variants]
    item_routes = dict(
        frappe.get_all("Item", filters={"name": ("in", templates)}, fields=["name", "route"], as_list=True)
    ) if templates else {}

    new_routes, redirects = plan_shared_route_fixes(web_items, item_routes)

    for name, route in new_routes.items():
        frappe.db.set_value("Website Item", name, "route", route, update_modified=False)

    added = add_redirects(redirects)
    print(f"Website Item routes changed: {len(new_routes)}. Route redirects added: {added}.")


def publish_templates_of_published_variants():
    """A published template with `pl_item = No` and published variants gets `pl_item = Yes`.
    Else the publish rule takes its page and its variant table off the website."""
    web_item = frappe.qb.DocType("Website Item")
    variant = frappe.qb.DocType("Website Item").as_("variant")
    item = frappe.qb.DocType("Item")
    published_templates = frappe.qb.from_(variant).select(variant.variant_of).where(variant.published == 1)
    templates = (
        frappe.qb.from_(web_item)
        .inner_join(item)
        .on(item.name == web_item.item_code)
        .select(item.name)
        .where(
            (web_item.published == 1)
            & (item.has_variants == 1)
            & (item.disabled == 0)
            & (Coalesce(item.pl_item, "No") != "Yes")
            & item.name.isin(published_templates)
        )
    ).run()

    for (name,) in templates:
        frappe.db.set_value("Item", name, "pl_item", "Yes", update_modified=False)
    print(f"Templates set to pl_item = Yes: {len(templates)}.")


def move_item_website_item_groups():
    """v12 kept Website Item Group rows on Item. Move each row to the Website Item of its Item.
    Delete it if the Item has no Website Item, or if the Website Item already has the group."""
    group = frappe.qb.DocType("Website Item Group")
    rows = (
        frappe.qb.from_(group)
        .select(group.name, group.parent, group.item_group)
        .where(group.parenttype == "Item")
    ).run(as_dict=True)

    moved = 0
    for row in rows:
        web_item = frappe.db.get_value("Website Item", {"item_code": row.parent})
        has_group = web_item and frappe.db.exists(
            "Website Item Group",
            {"parent": web_item, "parenttype": "Website Item", "item_group": row.item_group},
        )
        if not web_item or has_group:
            frappe.db.delete("Website Item Group", {"name": row.name})
            continue
        last_idx = frappe.db.get_value(
            "Website Item Group", {"parent": web_item, "parenttype": "Website Item"}, "max(idx)"
        )
        frappe.db.set_value(
            "Website Item Group",
            row.name,
            {
                "parent": web_item,
                "parenttype": "Website Item",
                "parentfield": "website_item_groups",
                "idx": (last_idx or 0) + 1,
            },
            update_modified=False,
        )
        moved += 1
    print(f"Website Item Group rows moved: {moved}. Deleted: {len(rows) - moved}.")


def fill_empty_web_fields_from_item():
    """Copy the v12 Item values to the Website Item fields that are empty."""
    fields = [field for field in V12_WEB_FIELDS if frappe.db.has_column("Item", field)]
    if not fields:
        return

    web_item = frappe.qb.DocType("Website Item")
    item = frappe.qb.DocType("Item")
    rows = (
        frappe.qb.from_(web_item)
        .inner_join(item)
        .on(item.name == web_item.item_code)
        .select(web_item.name, *[web_item[f] for f in fields], *[item[f].as_("item_" + f) for f in fields])
    ).run(as_dict=True)

    filled = 0
    for row in rows:
        changed = {f: row["item_" + f] for f in fields if not row[f] and row["item_" + f]}
        if changed:
            frappe.db.set_value("Website Item", row.name, changed, update_modified=False)
            filled += 1
    print(f"Website Items with empty web fields filled from Item: {filled}.")
