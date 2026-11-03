"""
Display helpers for Script Reports.

A report cell shows nothing for a 0 number, so the values that matter are easy to see.
Use `blank_zeros` on each row before it goes into the report data, and set
`"formatter": rigpl_erpnext.report.blank_zero_formatter` in the report JS
(`public/js/report_formatter.js`). Frappe shows an empty Float cell as "0.000"; the formatter
shows it as empty, so the "> 0" column filter removes it.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Sequence

import frappe
from frappe.utils.nestedset import get_descendants_of


def blank_if_zero(value: Any, precision: int = 3) -> Any:
    """Return None for a number that is 0 when rounded to `precision` decimals, for example 0 or
    1e-10. Return all other values as they are."""
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        if round(value, precision) == 0:
            return None
    return value


def blank_zeros(row: Sequence[Any], precision: int = 3) -> List[Any]:
    """Return the row with each number that rounds to 0 changed to None."""
    return [blank_if_zero(value, precision) for value in row]


def tree_and_descendants(doctype: str, name: str) -> List[str]:
    """Return a tree node (Territory, Sales Person, Customer Group) and all the nodes under it,
    for an `isin` report filter. 2 queries. The old reports read the tree without permissions."""
    if not frappe.db.exists(doctype, name):
        frappe.throw(frappe._("{0} {1} not found").format(doctype, name))
    return [name] + get_descendants_of(doctype, name, ignore_permissions=True)
