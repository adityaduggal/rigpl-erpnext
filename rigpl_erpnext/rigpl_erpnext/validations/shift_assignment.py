# -*- coding: utf-8 -*-
"""Keeps Shift Assignments as ranges of at most one calendar month (#196).

HR enters one row for each employee and day. On submit, a row is joined with the rows of the same
employee and Shift Type that end the day before it or start the day after it, while the range stays
in one month. The joined rows are cancelled.
"""
from typing import Dict, List

import frappe
from frappe.utils import add_days, getdate


def on_submit(doc, method):
    if not doc.end_date:
        return
    start, end = getdate(doc.start_date), getdate(doc.end_date)
    if not same_month(start, end):
        return

    joined = []
    before = get_neighbour(doc, "end_date", add_days(start, -1))
    if before and same_month(before.start_date, end):
        start = getdate(before.start_date)
        joined.append(before.name)
    after = get_neighbour(doc, "start_date", add_days(end, 1))
    if after and after.end_date and same_month(start, after.end_date):
        end = getdate(after.end_date)
        joined.append(after.name)
    if not joined:
        return

    for name in joined:
        frappe.db.set_value("Shift Assignment", name, "docstatus", 2)
        frappe.get_doc(dict(doctype="Comment", comment_type="Info", reference_doctype="Shift Assignment",
            reference_name=name, content="Cancelled: merged into {0}".format(doc.name))).insert(
            ignore_permissions=True)
    doc.db_set({"start_date": start, "end_date": end})


def get_neighbour(doc, field: str, value):
    rows = frappe.get_all("Shift Assignment", filters={"employee": doc.employee, "shift_type": doc.shift_type,
        "docstatus": 1, "status": "Active", field: value, "name": ("!=", doc.name)},
        fields=["name", "start_date", "end_date"], limit=1)
    return rows[0] if rows else None


def plan_month_runs(rows: List[Dict]) -> List[Dict]:
    """Groups the rows of one employee, sorted by start_date, into month runs.

    Returns [{"keep": name, "end_date": last day, "cancel": [names]}] for each run that joins rows.
    """
    runs = []
    run = None
    for row in rows:
        start, end = getdate(row["start_date"]), row["end_date"] and getdate(row["end_date"])
        joins = (run and run["end"] and end and row["shift_type"] == run["shift_type"]
            and start == add_days(run["end"], 1) and same_month(run["start"], end))
        if joins:
            run["end"] = end
            run["cancel"].append(row["name"])
            continue
        if run and run["cancel"]:
            runs.append(dict(keep=run["keep"], end_date=run["end"], cancel=run["cancel"]))
        run = dict(keep=row["name"], start=start, end=end, shift_type=row["shift_type"], cancel=[])
    if run and run["cancel"]:
        runs.append(dict(keep=run["keep"], end_date=run["end"], cancel=run["cancel"]))
    return runs


def same_month(first, second) -> bool:
    first, second = getdate(first), getdate(second)
    return (first.year, first.month) == (second.year, second.month)
