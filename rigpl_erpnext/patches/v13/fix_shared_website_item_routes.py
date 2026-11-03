import frappe
from frappe.query_builder.functions import Coalesce
from frappe.website.render import clear_cache

from rigpl_erpnext.utils.batch_write_utils import bulk_set_fields, bulk_update_rows
from rigpl_erpnext.utils.item_attribute_utils import chunks
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
      before its template. Copy the web fields from Item.
    The Item rules (`website_rigpl/item_sync.py`) are applied in `website_item_group_listing`,
    after `convert_item_yes_no_to_check`: here `pl_item` is still "Yes"/"No" text, and
    `cint("Yes")` is 0, so the sync would unpublish each Website Item.
    """
    fix_shared_routes()
    publish_templates_of_published_variants()
    move_item_website_item_groups()
    fill_empty_web_fields_from_item()
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

    bulk_update_rows("Website Item", {name: {"route": route} for name, route in new_routes.items()})

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

    bulk_set_fields("Item", {name: {"pl_item": "Yes"} for (name,) in templates}, {}, add_versions=False)
    print(f"Templates set to pl_item = Yes: {len(templates)}.")


def move_item_website_item_groups():
    """v12 kept Website Item Group rows on Item. Move each row to the Website Item of its Item.
    Delete it if the Item has no Website Item, or if the Website Item already has the group."""
    group = frappe.qb.DocType("Website Item Group")
    rows = (
        frappe.qb.from_(group)
        .select(group.name, group.parent, group.item_group)
        .where(group.parenttype == "Item")
        .orderby(group.parent)
        .orderby(group.idx)
    ).run(as_dict=True)

    web_items = get_web_items_by_item_code({row.parent for row in rows})
    groups, last_idx = get_web_item_groups(web_items.values())

    moves, deletes = {}, []
    for row in rows:
        web_item = web_items.get(row.parent)
        if not web_item or (web_item, row.item_group) in groups:
            deletes.append(row.name)
            continue
        groups.add((web_item, row.item_group))
        last_idx[web_item] = last_idx.get(web_item, 0) + 1
        moves[row.name] = {
            "parent": web_item,
            "parenttype": "Website Item",
            "parentfield": "website_item_groups",
            "idx": last_idx[web_item],
        }

    for chunk in chunks(deletes):
        frappe.db.delete("Website Item Group", {"name": ("in", chunk)})
    bulk_update_rows("Website Item Group", moves)
    print(f"Website Item Group rows moved: {len(moves)}. Deleted: {len(deletes)}.")


def get_web_items_by_item_code(item_codes):
    web_items = {}
    for chunk in chunks(item_codes):
        rows = frappe.get_all(
            "Website Item", filters={"item_code": ("in", chunk)}, fields=["name", "item_code"]
        )
        web_items.update({row.item_code: row.name for row in rows})
    return web_items


def get_web_item_groups(web_items):
    """({(web_item, item_group)}, {web_item: max idx}) of the groups on these Website Items."""
    groups, last_idx = set(), {}
    for chunk in chunks(web_items):
        rows = frappe.get_all(
            "Website Item Group",
            filters={"parenttype": "Website Item", "parent": ("in", chunk)},
            fields=["parent", "item_group", "idx"],
        )
        for row in rows:
            groups.add((row.parent, row.item_group))
            last_idx[row.parent] = max(last_idx.get(row.parent, 0), row.idx or 0)
    return groups, last_idx


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

    changes = {}
    for row in rows:
        changed = {f: row["item_" + f] for f in fields if not row[f] and row["item_" + f]}
        if changed:
            changes[row.name] = changed
    filled = bulk_update_rows("Website Item", changes)
    print(f"Website Items with empty web fields filled from Item: {filled}.")
