# -*- coding: utf-8 -*-
# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
"""
Work signature of the BOM Templates and the merge tools (#164). Two templates with the same
signature do the same work and differ only in the FG values, so they can be 1 template.
"""

import re

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import add_years, nowdate

from ...utils.item_attribute_utils import chunks
from .manufacturing_utils import (
    RULE_NUMBER,
    clear_fg_rules_cache,
    get_fg_attribute_rows,
    get_fg_failures,
    get_items_for_rules,
    group_text_rules,
    operation_applies,
    prepare_template_fg_rules,
    split_allowed_values,
)

BT = "BOM Template RIGPL"
RULE_TABLES = ("fg_restrictions", "rm_restrictions", "wip_restrictions")
MERGE_CHECK_ITEMS = 20


def read_template_data(templates):
    """
    Returns {template: {name, title, disabled, formula, no_of_rm_items, length_formula, operations,
    fg_restrictions, rm_restrictions, wip_restrictions, fg_rm_map}} with 4 queries for each chunk.
    """
    data = {}
    for chunk in chunks(templates):
        for d in frappe.get_all(BT, filters={"name": ("in", chunk)}, fields=[
                "name", "title", "disabled", "formula", "no_of_rm_items", "length_formula"]):
            data[d.name] = frappe._dict(d, operations=[], fg_rm_map=[], **{t: [] for t in RULE_TABLES})
        for row in frappe.get_all("BOM Operation", filters={"parenttype": BT, "parent": ("in", chunk)},
                fields=["parent", "idx", "operation", "condition_attribute", "condition_type", "condition_values"],
                order_by="parent, idx"):
            data[row.parent].operations.append(row)
        for row in frappe.get_all("Item Variant Restrictions", filters={"parenttype": BT, "parent": ("in", chunk)},
                fields=["parent", "parentfield", "idx", "attribute", "is_numeric", "allowed_values", "rule",
                        "value_source"], order_by="parent, parentfield, idx"):
            if row.parentfield in RULE_TABLES:
                data[row.parent][row.parentfield].append(row)
        for row in frappe.get_all("FG RM Grade Map", filters={"parenttype": BT, "parent": ("in", chunk),
                "parentfield": "fg_rm_map"}, fields=["parent", "fg_attribute", "fg_value", "rm_attribute", "rm_values"],
                order_by="parent, idx"):
            data[row.parent].fg_rm_map.append(row)
    return data


def normalise_rule(rule, almost=False):
    """The rule without spaces. With `almost`, each number is # (so + 0.5 and + 1.5 are the same)."""
    rule = re.sub(r"\s+", "", rule or "")
    return RULE_NUMBER.sub("#", rule) if almost else rule


def process_signature(bt):
    """The operations in order, No of RM Items and Length Formula: templates that are similar."""
    return tuple(op.operation for op in bt.operations), bt.no_of_rm_items or 0, bt.length_formula or 0


def work_signature(bt, almost=False):
    """
    Returns the work of a template (read_template_data) as a tuple: the operations with their
    conditions, the formula, No of RM Items, Length Formula, the RM and WIP numeric rules, the RM
    and WIP text attributes with their Value Source, and the mapped RM attributes. FG values are not
    in it, so templates that differ only in the FG values have the same signature.
    """
    operations = tuple(
        (op.operation, op.condition_attribute or "", op.condition_type or "",
         tuple(sorted(split_allowed_values(op.condition_values))))
        for op in bt.operations
    )
    rules = []
    for table in ("rm_restrictions", "wip_restrictions"):
        numeric = sorted(normalise_rule(d.rule, almost) for d in bt[table] if d.is_numeric == 1)
        text = sorted({(d.attribute, d.value_source or "") for d in bt[table] if d.is_numeric != 1})
        rules.append((table, tuple(numeric), tuple(text)))
    return (
        operations,
        normalise_rule(bt.formula),
        bt.no_of_rm_items or 0,
        bt.length_formula or 0,
        tuple(rules),
        tuple(sorted({d.rm_attribute for d in bt.fg_rm_map})),
    )


def joined_values(bt, table):
    """
    {attribute: shown values} of the text rows of 1 table (the rows of an attribute are OR). A row
    with a Value Source shows the source, and an RM attribute of the FG to RM Map shows the map.
    """
    shown = {}
    for d in bt[table]:
        if d.is_numeric != 1 and d.value_source:
            shown[d.attribute] = [f"({d.value_source})"]
    groups = group_text_rules([d for d in bt[table] if not d.value_source], no_means_any=table != "fg_restrictions")
    for attribute, values in groups.items():
        shown.setdefault(attribute, sorted(values) if values is not None else ["(any)"])
    if table == "rm_restrictions":
        for d in bt.fg_rm_map:
            shown.setdefault(d.rm_attribute, ["(FG to RM Map)"])
    return shown


def template_differences(bt, other):
    """
    Returns the differences of `other` against `bt` as text, apart from the FG values: the
    numeric rules, the RM and WIP values and the map. The FG values are what a merge joins.
    """
    diffs = []
    labels = {"rm_restrictions": "RM", "wip_restrictions": "WIP"}
    for table, label in labels.items():
        mine = sorted(normalise_rule(d.rule) for d in bt[table] if d.is_numeric == 1)
        theirs = sorted(normalise_rule(d.rule) for d in other[table] if d.is_numeric == 1)
        if mine != theirs:
            diffs.append(f"{label} rules: {'; '.join(theirs) or 'none'} (here: {'; '.join(mine) or 'none'})")
        mine_text, theirs_text = joined_values(bt, table), joined_values(other, table)
        for attribute in sorted(set(mine_text) | set(theirs_text)):
            if mine_text.get(attribute) != theirs_text.get(attribute):
                diffs.append(f"{label} {attribute}: {' / '.join(theirs_text.get(attribute, ['not set']))} "
                             f"(here: {' / '.join(mine_text.get(attribute, ['not set']))})")
    mine_map = sorted((d.fg_value, d.rm_attribute, d.rm_values) for d in bt.fg_rm_map)
    theirs_map = sorted((d.fg_value, d.rm_attribute, d.rm_values) for d in other.fg_rm_map)
    if mine_map != theirs_map:
        diffs.append("FG to RM Map is different")
    if work_signature(bt) != work_signature(other) and not diffs:
        diffs.append("Operations, formula or rule attributes are different")
    return diffs


def get_process_sheet_counts(templates, years=2):
    """{template: submitted Process Sheets in the last `years` years}, 1 query for each chunk."""
    counts = {}
    ps = frappe.qb.DocType("Process Sheet")
    for chunk in chunks(templates):
        rows = (
            frappe.qb.from_(ps)
            .select(ps.bom_template, Count(ps.name))
            .where(ps.docstatus == 1)
            .where(ps.date >= add_years(nowdate(), -years))
            .where(ps.bom_template.isin(chunk))
            .groupby(ps.bom_template)
            .run()
        )
        counts.update(dict(rows))
    return counts


MATCH_LEVELS = ("Exact", "Almost", "Same Operations")


def level_signature(bt, level):
    """Exact: work_signature. Almost: without the numbers of the rules. Same Operations: process_signature."""
    if level == "Same Operations":
        return process_signature(bt)
    return work_signature(bt, almost=level == "Almost")


def get_overlap_groups(level="Exact", templates=None):
    """
    Returns [[template data, ...], ...]: the groups of 2 or more active templates with the same
    signature at `level` (MATCH_LEVELS), the biggest group first.
    """
    if templates is None:
        templates = frappe.get_all(BT, filters={"disabled": 0}, pluck="name")
    data = read_template_data(templates)
    groups = {}
    for name in sorted(data):
        groups.setdefault(level_signature(data[name], level), []).append(data[name])
    return sorted((g for g in groups.values() if len(g) > 1), key=lambda g: (-len(g), g[0].name))


def item_result(bt, att_dict, known, so_detail=None):
    """
    Returns (operations, RM sizes, WIP sizes of the first RM) that template `bt` gives for 1 FG
    item, or None when the template does not match the item.
    """
    if get_fg_failures(prepare_template_fg_rules(bt.fg_restrictions), att_dict):
        return None
    fg_text = {att.attribute: att.attribute_value for att in att_dict}
    operations = [op.operation for op in bt.operations if operation_applies(op, fg_text)]
    rm_items = sorted(d.name for d in get_items_for_rules(bt.rm_restrictions, known, "rm", 1, bt.fg_rm_map))
    wip_items = []
    if rm_items and bt.wip_restrictions:
        from ...utils.item_utils import get_item_attributes

        wip_known = dict(known, rm=get_item_attributes(rm_items[0]))
        wip_items = sorted(d.name for d in get_items_for_rules(bt.wip_restrictions, wip_known, "wip", 1))
    return operations, rm_items, wip_items


def check_merge(merged, old, limit=MERGE_CHECK_ITEMS):
    """
    Replays (read only) up to `limit` distinct FG items of the submitted Process Sheets of the
    last 2 years of template `old`, and returns [{item, differences}] for the items where `merged`
    gives other operations, RM sizes or WIP sizes, or does not match.
    """
    ps = frappe.qb.DocType("Process Sheet")
    rows = (
        frappe.qb.from_(ps)
        .select(ps.production_item, ps.sales_order_item)
        .distinct()
        .where(ps.docstatus == 1)
        .where(ps.bom_template == old.name)
        .where(ps.date >= add_years(nowdate(), -2))
        .orderby(ps.production_item)
        .limit(limit)
        .run(as_dict=True)
    )
    results = []
    for row in rows:
        try:
            att_dict = get_fg_attribute_rows(row.production_item, row.sales_order_item)
        except frappe.ValidationError:
            frappe.clear_last_message()
            continue
        known = {"fg": att_dict}
        before, after = item_result(old, att_dict, known), item_result(merged, att_dict, known)
        if after is None:
            diffs = [_("{0} does not match the item").format(merged.name)]
        elif before is None:
            continue
        else:
            diffs = [item_list_change(label, b, a) for label, b, a in zip(("Operations", "RM", "WIP"), before, after)
                     if a != b]
        if diffs:
            results.append(frappe._dict(item=row.production_item, differences=diffs))
    return results, len(rows)


def item_list_change(label, before, after, shown=5):
    """Text of the change of a list: the operations in full, the items as added and removed."""
    if label == "Operations":
        return f"Operations: {' > '.join(after) or 'none'} (was {' > '.join(before) or 'none'})"
    parts = []
    for word, values in (("not given", sorted(set(before) - set(after))), ("new", sorted(set(after) - set(before)))):
        if values:
            more = f" and {len(values) - shown} more" if len(values) > shown else ""
            parts.append(f"{len(values)} {word}: {', '.join(values[:shown])}{more}")
    return f"{label}: " + "; ".join(parts)


@frappe.whitelist()
def get_similar_templates(bom_template):
    """
    For the Disable Similar Templates dialog: the active templates with the same process as
    `bom_template` (process_signature), with how close they are (Exact: the same work; Almost:
    only the numbers in the rules differ; Similar: the same operations), their differences,
    Process Sheets of the last 2 years and the merge check of their items. The closest come first.
    """
    frappe.has_permission(BT, "write", bom_template, throw=True)
    active = frappe.get_all(BT, filters={"disabled": 0}, pluck="name")
    data = read_template_data(set(active) | {bom_template})
    merged = data[bom_template]
    exact, almost, process = work_signature(merged), work_signature(merged, almost=True), process_signature(merged)
    kinds = ("Exact", "Almost", "Similar")
    similar = []
    for name in sorted(active):
        if name == bom_template or process_signature(data[name]) != process:
            continue
        if work_signature(data[name]) == exact:
            similar.append((name, "Exact"))
        elif work_signature(data[name], almost=True) == almost:
            similar.append((name, "Almost"))
        else:
            similar.append((name, "Similar"))
    similar.sort(key=lambda d: (kinds.index(d[1]), d[0]))
    counts = get_process_sheet_counts([name for name, _kind in similar])
    result = []
    for name, kind in similar:
        failures, checked = check_merge(merged, data[name])
        result.append(frappe._dict(
            template=name,
            title=data[name].title,
            kind=kind,
            differences=template_differences(merged, data[name]),
            process_sheets=counts.get(name, 0),
            items_checked=checked,
            merge_failures=failures,
        ))
    return result


@frappe.whitelist()
def disable_similar_templates(bom_template, templates):
    """
    Disables the `templates` and sets their Merged Into to `bom_template`, with a comment on each.
    It does not save the old templates, so their old rules do not need to pass the new checks.
    """
    templates = frappe.parse_json(templates) if isinstance(templates, str) else templates
    if frappe.db.get_value(BT, bom_template, "disabled"):
        frappe.throw(_("{0} is disabled. It cannot replace other templates.").format(bom_template))
    done = []
    for name in templates or []:
        if name == bom_template:
            continue
        frappe.has_permission(BT, "write", name, throw=True)
        frappe.db.set_value(BT, name, {"disabled": 1, "merged_into": bom_template})
        frappe.get_doc(BT, name).add_comment(
            "Comment", _("Disabled and merged into {0} by {1}.").format(
                frappe.get_desk_link(BT, bom_template), frappe.session.user)
        )
        done.append(name)
    clear_fg_rules_cache()
    return done

