#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
from typing import Iterable

import frappe
from frappe.utils import now

from .batch_write_utils import bulk_set_values
from .item_attribute_utils import chunks


def end_follow_ups(names: Iterable[str]):
    """Sets follow_up = 0 on the Communications and closes their Open ToDos (#150)."""
    names = list(names)
    if not names:
        return
    bulk_set_values("Communication", "follow_up", {name: 0 for name in names}, {name: 1 for name in names})
    todo = frappe.qb.DocType("ToDo")
    for chunk in chunks(names):
        (
            frappe.qb.update(todo)
            .set(todo.status, "Closed")
            .set(todo.modified, now())
            .where(todo.reference_type == "Communication")
            .where(todo.reference_name.isin(chunk))
            .where(todo.status == "Open")
        ).run()
