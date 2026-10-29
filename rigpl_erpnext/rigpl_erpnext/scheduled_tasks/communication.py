# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
from frappe.utils import now_datetime
import html2text
from .process_sheet_update import run_write
from ...utils.follow_up_utils import end_follow_ups


def create_follow_up_todos():
    """
    Runs each hour. Makes 1 ToDo and sends 1 email for each due follow-up that has no Open ToDo.
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
    todo.description = f"{comm.subject or ''}\n{html2text.html2text(comm.content or '')[0:100]}\n" \
                       f"{comm.reference_doctype or ''} {comm.reference_name or ''}"
    todo.insert()
    send_follow_up_email(comm.user, comm.owner, comm.subject or "", comm.content or "",
                         comm.reference_doctype or "", comm.reference_name or "")


def send_follow_up_email(user, sender, subject, content, ref_doc, ref_name):
    frappe.sendmail(recipients=user, sender=sender, subject="Follow Up for: " + subject,
                   content=content + "\n" + ref_doc + " " + ref_name)
