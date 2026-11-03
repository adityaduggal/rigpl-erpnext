"""
Display helpers for Script Reports.

A report cell shows nothing for a 0 number, so the values that matter are easy to see.
Use `blank_zeros` on each row before it goes into the report data, and set
`"formatter": rigpl_erpnext.report.blank_zero_formatter` in the report JS
(`public/js/report_formatter.js`). Frappe shows an empty Float cell as "0.000"; the formatter
shows it as empty, so the "> 0" column filter removes it.

Rows must respect permissions (#206). `frappe.get_all`, `frappe.qb` and `frappe.db.sql` skip role
permissions and User Permissions. Read the base DocType with `frappe.get_list`, or keep only the rows
whose name is in `permitted_names`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Set

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


def permitted_names(doctype: str, filters: Optional[Dict] = None) -> Set[str]:
    """Names of `doctype` that the session user can read, with User Permissions applied. Use it to
    limit the rows of a raw `frappe.qb` or `frappe.db.sql` read in a report."""
    return set(frappe.get_list(doctype, filters=filters or {}, pluck="name", limit_page_length=0))
