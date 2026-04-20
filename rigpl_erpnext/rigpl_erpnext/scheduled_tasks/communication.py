# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
from frappe.utils import nowdate, time_diff_in_hours, now_datetime
import html2text


def daily():
    st_time = time.time()
    now = now_datetime()
    
    # Fetch communications that need follow-up
    comm_dict = frappe.db.sql("""SELECT name, owner, user, communication_subtype, subject, content, 
        reference_doctype, reference_name, next_action_date 
        FROM `tabCommunication` 
        WHERE communication_type = 'Communication' AND follow_up = 1 AND next_action_date <= NOW()""", as_dict=1)

    if not comm_dict:
        print("No Communications to process.")
        return

    print(f"Total Communications to be Checked = {len(comm_dict)}")

    # Bulk fetch users to check if enabled
    users_to_fetch = list(set([c.user for c in comm_dict]))
    users_data = frappe.get_all("User", filters={"name": ["in", users_to_fetch]}, fields=["name", "enabled"])
    user_status_map = {u.name: u.enabled for u in users_data}

    # Bulk fetch existing ToDos for these communications
    comm_names = [c.name for c in comm_dict]
    todos = frappe.get_all("ToDo", filters={
        "reference_type": "Communication",
        "reference_name": ["in", comm_names]
    }, fields=["name", "reference_name", "assigned_by", "owner", "status"])
    
    todo_map = {}
    for t in todos:
        # Map by (reference_name, assigned_by, owner) to match original logic
        key = (t.reference_name, t.assigned_by, t.owner)
        todo_map[key] = t

    for comm in comm_dict:
        is_user_enabled = user_status_map.get(comm.user) == 1
        todo_key = (comm.name, comm.owner, comm.user)
        existing_todo = todo_map.get(todo_key)

        if not is_user_enabled:
            # Disable the Communication followup
            frappe.db.set_value("Communication", comm.name, "follow_up", 0)
            if existing_todo:
                if existing_todo.status != "Closed":
                    frappe.db.set_value("ToDo", existing_todo.name, "status", "Closed")
            continue

        if existing_todo:
            if existing_todo.status == "Open":
                if check_follow_up_time(comm.next_action_date, now) == 1:
                    send_follow_up_email(comm.user, comm.owner, comm.subject, comm.content,
                                         comm.reference_doctype, comm.reference_name)
            else:
                # Re-open ToDo
                frappe.db.set_value("ToDo", existing_todo.name, "status", "Open")
                if check_follow_up_time(comm.next_action_date, now) == 1:
                    send_follow_up_email(comm.user, comm.owner, comm.subject, comm.content,
                                         comm.reference_doctype, comm.reference_name)
        else:
            # Create new ToDo
            todo = frappe.new_doc("ToDo")
            todo.status = "Open"
            todo.priority = "High"
            todo.date = comm.next_action_date.date()
            todo.owner = comm.user
            todo.reference_type = "Communication"
            todo.reference_name = comm.name
            todo.type = comm.communication_subtype
            todo.assigned_by = comm.owner
            
            # Use local content instead of reloading doc
            clean_content = html2text.html2text(comm.content or "")[0:100]
            todo.description = f"{comm.subject or ''}\n{clean_content}\n{comm.reference_doctype} {comm.reference_name}"
            
            todo.insert(ignore_permissions=True)
            send_follow_up_email(comm.user, comm.owner, comm.subject, comm.content,
                                 comm.reference_doctype, comm.reference_name)

    tot_time = int(time.time() - st_time)
    print(f"Total Time Taken = {tot_time} seconds")


def check_follow_up_time(date_time, now):
    send_reminder = 0
    if 1 < (time_diff_in_hours(date_time, now)) < 2:
        send_reminder = 1
    return send_reminder


def send_follow_up_email(user, sender, subject, content, ref_doc, ref_name):

    if not frappe.get_cached_doc("RIGPL Settings").send_follow_up_email:
        return

    frappe.sendmail(
        recipients=user,
        sender=sender,
        subject=f"Follow Up for: {subject}",
        content=f"{content}\n{ref_doc} {ref_name}"
    )
