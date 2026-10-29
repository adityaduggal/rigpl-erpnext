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
    changes = bulk_set_fields(
        doctype,
        {name: {field: new} for name, new in new_by_name.items()},
        {name: {field: old} for name, old in old_by_name.items()},
    )
    return [(name, diff[0][1], diff[0][2]) for name, diff in changes.items()]


def bulk_set_fields(doctype: str, new_by_name: Dict[str, Dict], old_by_name: Dict[str, Dict],
        add_versions: bool = True) -> Dict[str, List[List]]:
    """
    Writes the fields of {name: {field: value}} that changed: one UPDATE for each set of new
    values and chunk of names, so at most 1 UPDATE for each changed document. `modified` is not
    changed. With `add_versions`, adds 1 Version for each changed document.
    Returns {name: [[field, old, new]]} of the changes.
    """
    changes = {}
    for name, new in new_by_name.items():
        old = old_by_name.get(name, {})
        diff = [[field, old.get(field), value] for field, value in new.items() if value != old.get(field)]
        if diff:
            changes[name] = diff
    names_by_values = {}
    for name, diff in changes.items():
        names_by_values.setdefault(tuple((field, new) for field, _old, new in diff), []).append(name)

    table = frappe.qb.DocType(doctype)
    for values, names in names_by_values.items():
        for chunk in chunks(names):
            query = frappe.qb.update(table)
            for field, value in values:
                query = query.set(table[field], value)
            query.where(table.name.isin(chunk)).run()

    clear_document_cache(doctype, changes)
    if add_versions:
        bulk_insert_versions(doctype, {name: {"changed": diff} for name, diff in changes.items()})
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
