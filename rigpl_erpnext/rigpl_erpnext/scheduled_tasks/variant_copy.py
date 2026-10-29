# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from time import time
from typing import List, Optional

import frappe
from frappe.model import no_value_fields
from frappe.utils import now
from frappe.website.render import clear_cache
from pypika import Order
from pypika.functions import Count, CurDate, IfNull
from rohit_common.utils.background_doc_processing import enqueue_once
from rigpl_erpnext.utils.batch_write_utils import bulk_set_fields, clear_document_cache
from rigpl_erpnext.utils.item_attribute_utils import chunks, get_attribute_rows
from rigpl_erpnext.utils.item_utils import get_description_data, make_description
from rigpl_erpnext.website_rigpl.item_sync import (
    get_pl_item_mismatches,
    make_missing_web_items,
    sync_web_items,
)

# The fields of Item Default that a variant takes from its template (see check_item_defaults).
DEFAULT_FIELDS = (
    "company",
    "default_warehouse",
    "default_price_list",
    "income_account",
    "buying_cost_center",
    "selling_cost_center",
)


def enqueue_check_wrong_variants():
    enqueue_once("rigpl_erpnext.rigpl_erpnext.scheduled_tasks.variant_copy.check_wrong_variants", queue="long", timeout=14400)


def check_wrong_variants():
    st_time = time()
    check_expired_items()
    sync_variants_from_templates()
    check_web_items()
    report_pl_item_mismatches()
    tot_time = int(time() - st_time)
    print(f"Total Time Taken = {tot_time} seconds")


def check_expired_items():
    # Not get_all: its filter reads a NULL end_of_life as 0001-01-01, so it is "expired".
    item = frappe.qb.DocType("Item")
    expired = [
        name
        for (name,) in frappe.qb.from_(item)
        .select(item.name)
        .where((item.end_of_life < CurDate()) & (item.disabled == 0))
        .run()
    ]
    bulk_set_fields(
        "Item",
        {name: {"disabled": 1} for name in expired},
        {name: {"disabled": 0} for name in expired},
        update_modified=True,
    )
    for name in expired:
        print("Item Code: " + name + " is Expired and hence Disabled")
    print("Total Items = " + str(len(expired)))
    frappe.db.commit()


def check_web_items():
    # sync_variants_from_templates changes long descriptions and clears no cache.
    made = make_missing_web_items()
    changed = sync_web_items()
    clear_cache()
    print(f"Website Items made = {made}, changed as per Item = {changed}")
    frappe.db.commit()


def report_pl_item_mismatches():
    """Item validate stops new mismatches (#107). This lists the ones from before it."""
    rows = get_pl_item_mismatches()
    if not rows:
        return
    message = "Templates that are not PL Items but have variants that are PL Items:\n" + "\n".join(
        f"{row.name}: {row.variants} variants" for row in rows
    )
    print(message)
    frappe.log_error(message, "PL Item of template and variants do not match")


def sync_variants_from_templates(template_names: Optional[List[str]] = None):
    """Copy the Variant Fields and Item Defaults of each active template to its enabled variants,
    and make the variant descriptions again. Only the rows that are different are written.
    Variants that do not match their template are not changed. They go in one Error Log.
    With `template_names`, only these templates."""
    copy_fields = get_variant_copy_fields()
    templates = get_templates(copy_fields, template_names)
    errors = []
    checked = changed = 0
    for sno, template in enumerate(templates, 1):
        data = load_variants(template.name, copy_fields)
        plan = plan_variant_changes(template, data, copy_fields)
        changed_items = write_variant_changes(plan, data)
        errors.extend(plan.errors)
        checked += len(data.variants)
        changed += len(changed_items)
        print(f"{sno}. Template: {template.name} Variants = {len(data.variants)}, "
            f"Changed = {len(changed_items)}, Errors = {len(plan.errors)}")
        frappe.db.commit()
    if errors:
        frappe.log_error("\n".join(f"{name}: {reason}" for name, reason in errors),
            "Variants that do not match their template")
    print(f"Templates = {len(templates)}, Variants checked = {checked}, changed = {changed}, "
        f"errors = {len(errors)}")


def get_variant_copy_fields() -> List[str]:
    """The Item fields of Variant Field (Item Variant Settings) that hold a value."""
    include = set(frappe.get_all("Variant Field", pluck="field_name"))
    return [
        field.fieldname
        for field in frappe.get_meta("Item").fields
        if field.fieldtype not in no_value_fields and not field.no_copy and field.fieldname in include
    ]


def get_templates(copy_fields, template_names=None):
    """Active templates with their copy fields, variant limit, variant count and Item Default."""
    item = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(item)
        .select(item.name, item.variant_limit, *[item[field] for field in copy_fields])
        .where(item.variant_of.isnull())
        .where(item.disabled == 0)
        .where(item.has_variants == 1)
        .where(IfNull(item.end_of_life, "2099-12-31") > CurDate())
        .orderby(item.modified, order=Order.desc)
    )
    if template_names:
        query = query.where(item.name.isin(template_names))
    templates = query.run(as_dict=True)
    names = [template.name for template in templates]
    counts, defaults = {}, {}
    for chunk in chunks(names):
        counts.update(
            frappe.qb.from_(item)
            .select(item.variant_of, Count(item.name))
            .where(item.variant_of.isin(chunk))
            .groupby(item.variant_of)
            .run()
        )
        # A later row wins, like copy_item_defaults.
        for row in frappe.get_all(
            "Item Default",
            filters={"parent": ("in", chunk), "parenttype": "Item"},
            fields=["parent", *DEFAULT_FIELDS],
            order_by="idx",
        ):
            defaults[row.parent] = row
    for template in templates:
        template.variant_count = counts.get(template.name, 0)
        template.item_default = defaults.get(template.name)
    return templates


def load_variants(template_name, copy_fields):
    """The enabled variants of one template, and their attribute rows, first Item Default and
    Website Item, with the data make_description needs."""
    variants = frappe.get_all(
        "Item",
        filters={"variant_of": template_name, "disabled": 0},
        fields=["name", "description", "item_name", "published_in_website", "image", *copy_fields],
        order_by="name",
    )
    names = [variant.name for variant in variants]
    data = frappe._dict(variants=variants, attributes={}, defaults={}, web_items={})
    if not names:
        data.description_data = ({}, set(), {})
        return data
    data.attributes = get_attribute_rows(names)
    all_rows = [row for rows in data.attributes.values() for row in rows]
    data.description_data = get_description_data([template_name], all_rows)
    for row in frappe.get_all(
        "Item Default",
        filters={"parent": ("in", names), "parenttype": "Item"},
        fields=["name", "parent", *DEFAULT_FIELDS],
        order_by="idx",
    ):
        data.defaults.setdefault(row.parent, row)
    for row in frappe.get_all(
        "Website Item",
        filters={"item_code": ("in", names)},
        fields=["name", "item_code", "web_long_description"],
    ):
        data.web_items.setdefault(row.item_code, row)
    return data


def plan_variant_changes(template, data, copy_fields):
    """Return the writes for the variants of `template` as
    {item_changes: {variant: {field: value}}, default_changes: {Item Default: {field: value}},
    web_changes: {Website Item: {field: value}}, errors: [(name, reason)]}. It does not read the DB."""
    plan = frappe._dict(item_changes={}, default_changes={}, web_changes={}, errors=[])
    if not data.variants:
        return plan
    if not template.item_default:
        plan.errors.append((template.name, "Item Defaults are Mandatory for Template"))
        return plan
    if template.variant_count > (template.variant_limit or 0):
        plan.errors.append((template.name, f"Template Limit reached. Set Limit = {template.variant_limit} "
            f"whereas total number of variants = {template.variant_count}"))
        return plan

    template_rows, numeric, value_desc = data.description_data
    template_rows = template_rows.get(template.name, {})
    for variant in data.variants:
        rows = data.attributes.get(variant.name, [])
        error = get_variant_error(variant, list(template_rows), rows)
        if not error:
            try:
                description, long_desc = make_description(rows, template_rows, numeric, value_desc)
            except frappe.ValidationError as e:
                error = str(e)
        if error:
            plan.errors.append((variant.name, error))
            continue

        new = {field: template[field] for field in copy_fields if variant[field] != template[field]}
        if variant.description != description:
            new.update(description=description, item_name=long_desc)
        if new:
            plan.item_changes[variant.name] = new

        default = data.defaults.get(variant.name)
        if default and any(default[field] != template.item_default[field] for field in DEFAULT_FIELDS):
            plan.default_changes[default.name] = {field: template.item_default[field] for field in DEFAULT_FIELDS}

        web_item = data.web_items.get(variant.name)
        if web_item and (web_item.web_long_description or "") != (long_desc or ""):
            plan.web_changes[web_item.name] = {"web_long_description": long_desc}
    return plan


def get_variant_error(variant, template_attributes, rows):
    """The first reason, as in validate_variants, why a variant does not match its template."""
    if variant.published_in_website == 1 and variant.image is None:
        return "For Website Items, Website Image is Mandatory"
    if len(rows) != len(template_attributes):
        return "number of attributes not as per the template"
    for idx, (row, attribute) in enumerate(zip(rows, template_attributes), 1):
        if row.attribute != attribute:
            return f"Row# {idx} should have {attribute} as per the template"
    return None


def write_variant_changes(plan, data):
    """Write the plan. Return the names of the variants that changed."""
    changed = bulk_set_fields(
        "Item", plan.item_changes, {variant.name: variant for variant in data.variants}, update_modified=True
    )
    defaults = {row.name: row for row in data.defaults.values()}
    changed_defaults = bulk_set_fields("Item Default", plan.default_changes, defaults, add_versions=False)
    touch_items([defaults[name].parent for name in changed_defaults if defaults[name].parent not in changed])
    web_items = {row.name: row for row in data.web_items.values()}
    bulk_set_fields("Website Item", plan.web_changes, web_items, add_versions=False, update_modified=True)
    return set(changed) | {defaults[name].parent for name in changed_defaults}


def touch_items(names):
    """Set `modified` of Items whose child rows changed."""
    item = frappe.qb.DocType("Item")
    for chunk in chunks(names):
        frappe.qb.update(item).set(item.modified, now()).set(item.modified_by, frappe.session.user).where(
            item.name.isin(chunk)
        ).run()
    clear_document_cache("Item", names)
