import json
import os

import frappe
from frappe.modules.utils import sync_customizations_for_doctype

from rigpl_erpnext.website_rigpl.route_sync import rebuild_routes

SLUGS_FILE = ("website_rigpl", "website_data", "route_slugs.json")


def execute():
    """
    Make the short website routes (#97) with a 301 redirect from each old route.
    Idempotent: a second run changes nothing.

    v13 migrate runs the patches before it syncs the custom fields, so this patch syncs the
    Website-RIGPL custom fields and RIGPL Settings first.
    """
    sync_website_custom_fields()
    frappe.reload_doc("rigpl_erpnext", "doctype", "rigpl_settings")
    frappe.clear_document_cache("RIGPL Settings", "RIGPL Settings")
    # Website Item validate reads the template Website Item by item_code.
    frappe.db.add_index("Website Item", ["item_code"])

    print(f"Item Groups given a Website Slug: {seed_group_slugs()}.")
    counts = rebuild_routes()
    print(
        "Routes changed: {groups} Item Groups, {website_items} Website Items. Redirects: "
        "{added} added, {retargeted} retargeted, {deleted} deleted. Errors: {errors} "
        "(see Error Log).".format(**counts)
    )


def sync_website_custom_fields():
    folder = frappe.get_app_path("rigpl_erpnext", "website_rigpl", "custom")
    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".json"):
            with open(os.path.join(folder, fname)) as f:
                sync_customizations_for_doctype(json.load(f), folder, fname)


def seed_group_slugs() -> int:
    """Set the Website Slug and Include in URL of each group in the file, if its Website Slug
    is empty. A slug that an editor set does not change."""
    with open(frappe.get_app_path("rigpl_erpnext", *SLUGS_FILE)) as f:
        slugs = json.load(f)

    empty = frappe.get_all(
        "Item Group",
        filters={"name": ("in", list(slugs)), "website_slug": ("is", "not set")},
        pluck="name",
    )
    for name in empty:
        frappe.db.set_value("Item Group", name, slugs[name], update_modified=False)
    return len(empty)
