# -*- coding: utf-8 -*-
#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
Batched writes for the long scheduled jobs. They change many documents without a query
for each document, and keep the Version history that Document.save() would write.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

import frappe
from frappe.utils import now
from pypika.terms import Values

from .item_attribute_utils import chunks

VERSION_FIELDS = (
    "name",
    "creation",
    "modified",
    "modified_by",
    "owner",
    "docstatus",
    "ref_doctype",
    "docname",
    "data",
)


def bulk_set_values(doctype: str, field: str, new_by_name: Dict, old_by_name: Dict) -> List[Tuple]:
    """
    Writes `field` only for the names whose value changed: one UPDATE for each new value and
    chunk of names. `modified` is not changed, since the jobs only write computed values.
    Returns the changes as [(name, old, new)].
    """
    changes = [
        (name, old_by_name.get(name), new)
        for name, new in new_by_name.items()
        if new != old_by_name.get(name)
    ]
    names_by_value = {}
    for name, _old, new in changes:
        names_by_value.setdefault(new, []).append(name)

    table = frappe.qb.DocType(doctype)
    for value, names in names_by_value.items():
        for chunk in chunks(names):
            frappe.qb.update(table).set(table[field], value).where(table.name.isin(chunk)).run()

    clear_document_cache(doctype, [name for name, _old, _new in changes])
    bulk_insert_versions(doctype, {name: {"changed": [[field, old, new]]} for name, old, new in changes})
    return changes


def bulk_insert_rows(doctype: str, fields: Iterable[str], rows: List[Tuple], update_fields=()):
    """
    Inserts rows in chunks. With `update_fields`, an existing row (same name) gets those
    fields updated instead (INSERT ... ON DUPLICATE KEY UPDATE).
    frappe.db.bulk_insert is not used: in this version it never inserts the last row.
    """
    table = frappe.qb.DocType(doctype)
    fields = list(fields)
    for start in range(0, len(rows), 1000):
        query = frappe.qb.into(table).columns(*fields).insert(*rows[start : start + 1000])
        for field in update_fields:
            query = query.on_duplicate_key_update(table[field], Values(table[field]))
        query.run()


def bulk_insert_versions(doctype: str, diffs: Dict[str, Dict]):
    """
    Adds a Version for each {docname: diff}, if the doctype tracks changes. A diff has the
    keys of frappe.core.doctype.version.version.get_diff (changed, added, row_changed...).
    """
    if not diffs or not frappe.get_meta(doctype).track_changes:
        return
    timestamp, user = now(), frappe.session.user
    rows = []
    for docname, diff in diffs.items():
        data = {
            "changed": [],
            "added": [],
            "removed": [],
            "row_changed": [],
            "data_import": None,
            "updater_reference": None,
        }
        data.update(diff)
        rows.append(
            (
                frappe.generate_hash(length=10),
                timestamp,
                timestamp,
                user,
                user,
                0,
                doctype,
                docname,
                frappe.as_json(data, indent=None, separators=(",", ":")),
            )
        )
    bulk_insert_rows("Version", VERSION_FIELDS, rows)


def clear_document_cache(doctype: str, names: Iterable[str]):
    """Removes the cached docs like frappe.db.set_value does (Redis only, no DB query)."""
    for name in names:
        frappe.clear_document_cache(doctype, name)
