# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
"""The active BOM Templates that do the same work and can be 1 template (#164)."""

import frappe

from rigpl_erpnext.manufacturing_rigpl.utils.bom_template_merge_utils import (
    get_overlap_groups,
    get_process_sheet_counts,
    joined_values,
    template_differences,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "group", "label": "Group", "fieldtype": "Int", "width": 70},
        {"fieldname": "bom_template", "label": "BOM Template", "fieldtype": "Link", "options": "BOM Template RIGPL",
         "width": 120},
        {"fieldname": "title", "label": "Title", "fieldtype": "Data", "width": 260},
        {"fieldname": "process_sheets", "label": "PS (2 Years)", "fieldtype": "Int", "width": 90},
        {"fieldname": "operations", "label": "Operations", "fieldtype": "Data", "width": 260},
        {"fieldname": "fg_values", "label": "FG Values", "fieldtype": "Data", "width": 360},
        {"fieldname": "differences", "label": "Differences from the First Template", "fieldtype": "Data", "width": 420},
    ]


def get_data(filters):
    """
    Returns 1 row for each template of each group of 2 or more active templates with the same work
    at the Match Level (Exact; Almost: the numbers in the rules can differ; Same Operations). The FG
    Values are what the merged template must hold. The Differences are the RM and WIP rule
    differences that are not FG values.
    """
    groups = [g for g in get_overlap_groups(filters.match_level or "Exact") if group_matches(g, filters)]
    counts = get_process_sheet_counts([bt.name for group in groups for bt in group])
    data = []
    for number, group in enumerate(groups, start=1):
        first = group[0]
        for bt in group:
            fg = joined_values(bt, "fg_restrictions")
            data.append({
                "group": number,
                "bom_template": bt.name,
                "title": bt.title,
                "process_sheets": counts.get(bt.name) or None,
                "operations": " > ".join(op.operation for op in bt.operations),
                "fg_values": "; ".join(f"{attribute}: {' / '.join(values)}" for attribute, values in fg.items()),
                "differences": "; ".join(template_differences(first, bt)) if bt is not first else "",
            })
    return data


def group_matches(group, filters):
    """True when a template of the group allows the Base Material and Tool Type of the filters."""
    wanted = {"Base Material": filters.bm, "Tool Type": filters.tt}
    for bt in group:
        fg = joined_values(bt, "fg_restrictions")
        if all(not value or value in fg.get(attribute, []) for attribute, value in wanted.items()):
            return True
    return False
