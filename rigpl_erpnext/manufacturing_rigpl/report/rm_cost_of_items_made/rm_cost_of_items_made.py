# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
"""
The real cost of the RM of the items made in 2 periods, by FG attributes. For example the RM cost
of each HSS Punch in 2025 against 2026.
"""

import frappe
from frappe.utils import add_years, flt, get_first_day, getdate, nowdate

from rigpl_erpnext.manufacturing_rigpl.utils.rm_cost_utils import (
    get_fg_attribute_values,
    get_rm_costs,
    get_rm_job_cards,
    get_rm_rows,
)
from rigpl_erpnext.utils.report_utils import blank_zeros

DEFAULT_GROUP_BY = ["Base Material", "Tool Type"]
PERIOD_FIELDS = ("pieces", "rm_qty", "rm_cost")


def execute(filters=None):
    filters = frappe._dict(filters or {})
    group_by = get_group_by(filters)
    return get_columns(group_by, filters), get_data(filters, group_by)


def get_group_by(filters):
    group_by = filters.group_by or DEFAULT_GROUP_BY
    return frappe.parse_json(group_by) if isinstance(group_by, str) else list(group_by)


def get_periods(filters):
    """[(label, from, to)] of the 2 periods. Default: last year, and this year to today."""
    today = getdate(nowdate())
    this_year = get_first_day(today.replace(month=1))
    p1 = (getdate(filters.from_date_1 or add_years(this_year, -1)), getdate(filters.to_date_1 or add_years(today, -1)))
    p2 = (getdate(filters.from_date_2 or this_year), getdate(filters.to_date_2 or today))
    return [(f"P1 {p1[0]} to {p1[1]}", *p1), (f"P2 {p2[0]} to {p2[1]}", *p2)]


def get_columns(group_by, filters):
    columns = [{"fieldname": f"att_{i}", "label": attribute, "fieldtype": "Data", "width": 130}
               for i, attribute in enumerate(group_by)]
    if filters.show_items:
        columns.append({"fieldname": "item", "label": "FG Item", "fieldtype": "Link", "options": "Item", "width": 130})
        columns.append({"fieldname": "rm_items", "label": "RM Items", "fieldtype": "Data", "width": 200})
    for n, (label, _from, _to) in enumerate(get_periods(filters), start=1):
        columns += [
            {"fieldname": f"p{n}_pieces", "label": f"Pieces P{n}", "fieldtype": "Float", "width": 90},
            {"fieldname": f"p{n}_rm_qty", "label": f"RM Qty P{n}", "fieldtype": "Float", "width": 90},
            {"fieldname": f"p{n}_rm_cost", "label": f"RM Cost P{n}", "fieldtype": "Currency", "width": 110},
            {"fieldname": f"p{n}_per_piece", "label": f"RM Cost per Piece P{n}", "fieldtype": "Currency", "width": 120},
        ]
    columns.append({"fieldname": "change", "label": "Change % (per Piece)", "fieldtype": "Percent", "width": 110})
    return columns


def get_data(filters, group_by):
    """
    Returns 1 row for each group of FG attribute values (and FG item with Show Items). RM cost is
    the cost of the RM rows of the Stock Entries of the submitted RM Job Cards (the real FIFO cost).
    Pieces are the completed and rejected qty of these Job Cards.
    """
    wanted = {attribute: value for attribute, value in (("Base Material", filters.bm), ("Tool Type", filters.tt)) if value}
    attributes = list(dict.fromkeys(group_by + list(wanted)))
    groups = {}
    for n, (_label, from_date, to_date) in enumerate(get_periods(filters), start=1):
        job_cards = get_rm_job_cards(from_date, to_date, filters.bom_template)
        if filters.item_template:
            templates = dict(frappe.get_all("Item", filters={"name": ("in", list({d.production_item for d in job_cards}))},
                fields=["name", "variant_of"], as_list=True)) if job_cards else {}
            job_cards = [d for d in job_cards if templates.get(d.production_item) == filters.item_template]
        values = get_fg_attribute_values(job_cards, attributes)
        job_cards = [d for d in job_cards if all(values[d.name].get(a) == v for a, v in wanted.items())]
        names = [d.name for d in job_cards]
        rm_rows, costs = get_rm_rows(names), get_rm_costs(names)
        for jc in job_cards:
            key = tuple(values[jc.name].get(attribute) or "" for attribute in group_by)
            if filters.show_items:
                key += (jc.production_item,)
            g = groups.setdefault(key, frappe._dict(rm_items=set(), **{f"p{i}_{f}": 0 for i in (1, 2) for f in PERIOD_FIELDS}))
            g[f"p{n}_pieces"] += flt(jc.total_completed_qty) + flt(jc.total_rejected_qty)
            for row in rm_rows.get(jc.name, []):
                qty, cost = costs.get((jc.name, row.item_code), (0, 0))
                g[f"p{n}_rm_qty"] += qty
                g[f"p{n}_rm_cost"] += cost
                g.rm_items.add(row.item_code)
    data = []
    for key in sorted(groups):
        g = groups[key]
        row = list(key)
        if filters.show_items:
            row.append(", ".join(sorted(g.rm_items)))
        per_piece = []
        for n in (1, 2):
            pieces, cost = g[f"p{n}_pieces"], g[f"p{n}_rm_cost"]
            per_piece.append(cost / pieces if pieces else 0)
            row += [pieces, g[f"p{n}_rm_qty"], cost, per_piece[-1]]
        row.append((per_piece[1] - per_piece[0]) / per_piece[0] * 100 if per_piece[0] and per_piece[1] else 0)
        data.append(blank_zeros(row))
    return data
