"""
Creates the default SEO records (#263). The after_migrate hook seed_seo_once runs it one time
on each site. The button in SEO Settings runs it again. A record that exists is not changed.
"""
from __future__ import annotations

from typing import List

import frappe
from frappe.modules.patch_handler import update_patch_log

from rigpl_erpnext.website_rigpl.seo import meta

from .records import HOME_RULE, SCHEMA_TEMPLATES, SEO_RULES, SETTINGS

SEED_PATCH = "rigpl_erpnext.patches.manual.seed_seo_records"
SEED_ERROR_TITLE = "RIGPL SEO seed failed"


def seed_seo_once():
    """after_migrate. A failed seed must not stop the migrate."""
    if frappe.db.exists("Patch Log", {"patch": SEED_PATCH}):
        return

    # A savepoint keeps the other after_migrate work in this transaction.
    frappe.db.savepoint("rigpl_seo_seed")
    try:
        create_missing_records()
        update_patch_log(SEED_PATCH)
    except Exception as e:
        frappe.db.rollback(save_point="rigpl_seo_seed")
        meta.clear_caches()
        frappe.log_error(frappe.get_traceback(), SEED_ERROR_TITLE)
        print(
            f"\nrigpl_erpnext: the SEO records are not created: {e}\n"
            f"  Correct the error, then run: bench --site {frappe.local.site} migrate\n"
        )


def create_missing_records() -> List[str]:
    """The names of the new records."""
    created = insert_missing("Schema Template", "template_name", SCHEMA_TEMPLATES)
    created += insert_missing("SEO Rule", "rule_name", SEO_RULES + get_home_rules())
    fill_settings()
    return created


def get_home_rules() -> list:
    """The rule of the home page. Empty if the home page of Website Settings is no Web Page."""
    route = frappe.db.get_single_value("Website Settings", "home_page")
    if not route or not frappe.db.exists("Web Page", {"route": route, "published": 1}):
        return []
    return [dict(HOME_RULE, route_pattern=route)]


def has_web_template(record: dict) -> bool:
    """False for a block template whose Web Template the site does not have."""
    name = record.get("web_template")
    return not name or bool(frappe.db.exists("Web Template", name))


def insert_missing(doctype: str, name_field: str, records: list) -> List[str]:
    records = [record for record in records if has_web_template(record)]
    names = [record[name_field] for record in records]
    existing = set(frappe.get_all(doctype, filters={"name": ["in", names]}, pluck="name"))
    created = []
    for record in records:
        if record[name_field] in existing:
            continue
        doc = frappe.get_doc(dict(record, doctype=doctype, enabled=1))
        # migrate must not render website pages
        doc.flags.skip_route_check = True
        doc.insert(ignore_permissions=True)
        created.append(doc.name)
    return created


def fill_settings():
    settings = frappe.get_doc("SEO Settings", "SEO Settings")
    empty = {field: value for field, value in SETTINGS.items() if not settings.get(field)}
    if empty:
        settings.update(empty)
        settings.save(ignore_permissions=True)
