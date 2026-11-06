#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
from typing import Iterable, Tuple

import frappe
from frappe.utils import now
from pypika.terms import Tuple as SqlTuple

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


def end_party_follow_ups(parties: Iterable[Tuple[str, str]], exclude: Iterable[str] = ()):
    """
    Ends the follow-ups of all users on the (reference_doctype, reference_name) parties, due or
    not. A Customer also matches its Contacts: the older DCRs made their calls against the Contact.
    """
    from .sales_utils import get_link_contacts

    parties = {(doctype, name) for doctype, name in parties if doctype and name}
    customers = [name for doctype, name in parties if doctype == "Customer"]
    for contacts in get_link_contacts("Customer", customers).values():
        parties.update(("Contact", contact.name) for contact in contacts)
    comm = frappe.qb.DocType("Communication")
    exclude = set(exclude)
    names = []
    for chunk in chunks(sorted(parties)):
        rows = (
            frappe.qb.from_(comm)
            .select(comm.name)
            .where(comm.communication_type == "Communication")
            .where(comm.follow_up == 1)
            .where(SqlTuple(comm.reference_doctype, comm.reference_name).isin([SqlTuple(*p) for p in chunk]))
        ).run()
        names += [row[0] for row in rows if row[0] not in exclude]
    end_follow_ups(names)
