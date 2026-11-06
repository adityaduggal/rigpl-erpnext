# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
from frappe.utils import escape_html, now_datetime
from .process_sheet_update import run_write
from ...utils.follow_up_utils import end_follow_ups


def create_follow_up_todos():
    """
    Runs each hour. Makes 1 ToDo for each due follow-up that has no Open ToDo. The ERPNext Email
    Digest mails each user the list of their Open ToDos.
    Ends the follow-ups of empty, deleted or disabled users. A closed ToDo is never opened again.
    """
    st_time = time.time()
    due = get_due_follow_ups()
    print(f"Total Communications to be Checked = {len(due)}")
    process_follow_ups(due)
    print(f"Total Time Taken = {int(time.time() - st_time)} seconds")


def get_due_follow_ups(names=None):
    values = {"now": now_datetime()}
    name_cond = ""
    if names is not None:
        if not names:
            return []
        name_cond = "AND c.name IN %(names)s"
        values["names"] = tuple(names)
    return frappe.db.sql(f"""SELECT c.name, c.owner, c.user, c.subject, c.content, c.reference_doctype,
        c.reference_name, c.communication_subtype, c.next_action_date, IFNULL(u.enabled, 0) AS user_enabled
        FROM `tabCommunication` c LEFT JOIN `tabUser` u ON u.name = c.user
        WHERE c.communication_type = 'Communication' AND c.follow_up = 1 AND c.next_action_date <= %(now)s
        {name_cond}
        AND (IFNULL(u.enabled, 0) = 0 OR NOT EXISTS (SELECT 1 FROM `tabToDo` t
            WHERE t.reference_type = 'Communication' AND t.reference_name = c.name AND t.status = 'Open'))""",
        values, as_dict=1)


def process_follow_ups(due):
    end_follow_ups([comm.name for comm in due if not comm.user_enabled])
    for comm in due:
        if comm.user_enabled:
            run_write("follow_up_todo", lambda: make_todo(comm), f"ToDo not made for Communication {comm.name}")


def make_todo(comm):
    todo = frappe.new_doc("ToDo")
    todo.status = "Open"
    todo.priority = "High"
    todo.date = comm.next_action_date.date()
    todo.owner = comm.user
    todo.reference_type = "Communication"
    todo.reference_name = comm.name
    todo.assigned_by = comm.owner
    todo.description = get_todo_description(comm)
    todo.insert()


def get_todo_description(comm):
    """The subject, the full call notes and the party, as HTML for the ToDo Text Editor."""
    party = ""
    if comm.reference_doctype and comm.reference_name:
        party = frappe.get_desk_link(comm.reference_doctype, comm.reference_name)
    return "<p><b>{}</b></p>{}<p>{}</p>".format(escape_html(comm.subject or ""),
        comm.content or "", party)
