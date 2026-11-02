# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
"""The RM that the Job Cards used above their Calculated Qty, by value, from actual data (#164)."""

import frappe
from frappe.utils import cint, flt

from rigpl_erpnext.manufacturing_rigpl.utils.manufacturing_utils import get_rm_excess, get_rm_excess_settings
from rigpl_erpnext.manufacturing_rigpl.utils.rm_cost_utils import get_rm_costs, get_rm_job_cards, get_rm_rows
from rigpl_erpnext.utils.report_utils import blank_zeros

GROUPS = {"BOM Template": "bom_template", "FG Item": "production_item", "RM Item": "item_code"}
NUMBERS = ("calculated_qty", "qty", "excess_qty", "used_value", "excess_value")


def execute(filters=None):
    filters = frappe._dict(filters or {})
    rows = get_rows(filters)
    if filters.group_by in GROUPS:
        return get_group_columns(filters.group_by), get_groups(rows, GROUPS[filters.group_by])
    return get_columns(), [blank_zeros([row[c["fieldname"]] for c in get_columns()]) for row in rows]


def get_columns():
    return [
        {"fieldname": "job_card", "label": "Job Card", "fieldtype": "Link", "options": "Process Job Card RIGPL", "width": 110},
        {"fieldname": "posting_date", "label": "Date", "fieldtype": "Date", "width": 90},
        {"fieldname": "bom_template", "label": "BOM Template", "fieldtype": "Link", "options": "BOM Template RIGPL", "width": 110},
        {"fieldname": "production_item", "label": "FG Item", "fieldtype": "Link", "options": "Item", "width": 130},
        {"fieldname": "item_code", "label": "RM Item", "fieldtype": "Link", "options": "Item", "width": 130},
        {"fieldname": "calculated_qty", "label": "Calculated Qty", "fieldtype": "Float", "width": 100},
        {"fieldname": "qty", "label": "Used Qty", "fieldtype": "Float", "width": 90},
        {"fieldname": "excess_qty", "label": "Excess Qty", "fieldtype": "Float", "width": 90},
        {"fieldname": "rate", "label": "RM Rate", "fieldtype": "Currency", "width": 90},
        {"fieldname": "used_value", "label": "RM Value Used", "fieldtype": "Currency", "width": 110},
        {"fieldname": "excess_value", "label": "Excess Value", "fieldtype": "Currency", "width": 100},
        {"fieldname": "allowed", "label": "Allowed Excess", "fieldtype": "Currency", "width": 100},
        {"fieldname": "over_limit", "label": "Over Limit", "fieldtype": "Check", "width": 80},
        {"fieldname": "bypass", "label": "Bypass", "fieldtype": "Check", "width": 70},
        {"fieldname": "user", "label": "User", "fieldtype": "Link", "options": "User", "width": 140},
    ]


def get_rows(filters):
    """
    Returns 1 row for each RM row of the submitted RM Job Cards in the dates. The rate is the real
    cost of the RM in the Stock Entry of the Job Card (Stock Ledger), not today's rate. The allowed
    excess is the rule of today (RIGPL Settings) for the RM value of the Job Card.
    """
    job_cards = get_rm_job_cards(filters.from_date, filters.to_date, filters.bom_template)
    names = [d.name for d in job_cards]
    rm_rows, costs, settings = get_rm_rows(names), get_rm_costs(names), get_rm_excess_settings()
    data = []
    for jc in job_cards:
        rows = rm_rows.get(jc.name, [])
        rates = {}
        for row in rows:
            qty, value = costs.get((jc.name, row.item_code), (0, 0))
            rates[row.item_code] = value / qty if qty else 0
        excess = get_rm_excess(rows, rates, settings)
        over = excess.excess_value > excess.allowed
        for row in rows:
            rate = rates[row.item_code]
            excess_qty = max(0, flt(row.qty) - flt(row.calculated_qty))
            line = frappe._dict(
                job_card=jc.name, posting_date=jc.posting_date, bom_template=jc.bom_template,
                production_item=jc.production_item, item_code=row.item_code, calculated_qty=row.calculated_qty,
                qty=row.qty, excess_qty=excess_qty, rate=rate, used_value=flt(row.qty) * rate,
                excess_value=excess_qty * rate, allowed=excess.allowed, over_limit=cint(over),
                bypass=row.bypass_qty_check, user=jc.modified_by,
            )
            if filters.over_limit_only and not over:
                continue
            if filters.bypassed_only and not row.bypass_qty_check:
                continue
            data.append(line)
    return data


def get_group_columns(group_by):
    key = next(c for c in get_columns() if c["fieldname"] == GROUPS[group_by])
    return [key] + [
        {"fieldname": "job_cards", "label": "Job Cards", "fieldtype": "Int", "width": 90},
        {"fieldname": "calculated_qty", "label": "Calculated Qty", "fieldtype": "Float", "width": 110},
        {"fieldname": "qty", "label": "Used Qty", "fieldtype": "Float", "width": 100},
        {"fieldname": "excess_qty", "label": "Excess Qty", "fieldtype": "Float", "width": 100},
        {"fieldname": "used_value", "label": "RM Value Used", "fieldtype": "Currency", "width": 120},
        {"fieldname": "excess_value", "label": "Excess Value", "fieldtype": "Currency", "width": 110},
        {"fieldname": "excess_percent", "label": "Excess % of Value", "fieldtype": "Percent", "width": 110},
        {"fieldname": "over_limit", "label": "Over Limit", "fieldtype": "Int", "width": 90},
        {"fieldname": "bypassed", "label": "Bypassed", "fieldtype": "Int", "width": 90},
    ]


def get_groups(rows, key):
    """The rows summed by `key`, the highest Excess Value first."""
    groups = {}
    for row in rows:
        g = groups.setdefault(row[key], frappe._dict({key: row[key], "job_cards": set(), "over": set(),
            "bypassed": 0, **{n: 0 for n in NUMBERS}}))
        g.job_cards.add(row.job_card)
        if row.over_limit:
            g.over.add(row.job_card)
        g.bypassed += cint(row.bypass)
        for n in NUMBERS:
            g[n] += flt(row[n])
    data = []
    for g in sorted(groups.values(), key=lambda g: -g.excess_value):
        percent = g.excess_value / g.used_value * 100 if g.used_value else 0
        data.append(blank_zeros([g[key], len(g.job_cards), g.calculated_qty, g.qty, g.excess_qty, g.used_value,
            g.excess_value, percent, len(g.over), g.bypassed]))
    return data
