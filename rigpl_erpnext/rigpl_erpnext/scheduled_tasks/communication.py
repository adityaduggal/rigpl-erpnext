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
    '''First Check for Communications which can be used for making TODO only communication_type == "Communication" 
    and communication_subtype == "Sales Related" and next_action_date IS NOT NULL'''
    comm_dict = frappe.db.sql("""SELECT name, owner, user FROM `tabCommunication` WHERE communication_type = 'Communication' 
    AND follow_up = 1 AND next_action_date <= NOW()""", as_dict=1)

    print(f"Total Communications to be Checked = {len(comm_dict)}")

    for comm in comm_dict:
        '''Check if the communication is already in TODO for the user and Open.TODO Assigned by == Owner of the 
        Communication TODO Owner  == User of Communication. Also check if User is Disabled then Follow Up and TODO
        Should be Closed'''
        disabled_user = 0
        user = frappe.db.sql("""SELECT name, enabled FROM `tabUser` WHERE name = '%s'""" % comm.user, as_dict=1)

        todo = frappe.db.sql("""SELECT name FROM `tabToDo` WHERE reference_type = 'Communication' 
        AND reference_name = '%s' AND assigned_by = '%s' AND owner = '%s' """ % (comm.name, comm.owner, comm.user),
                             as_dict=1)

        if user[0].enabled != 1:
            disabled_user += 1
            # Disable the Communication followup and corresponding ToD should be closed
            frappe.db.set_value("Communication", comm.name, "follow_up", 0)
            if todo:
                todo_doc = frappe.get_doc("ToDo", todo[0].name)
                todo_doc.status = "Closed"
                try:
                    todo_doc.save()
                except:
                    print(f"Some Error with {todo_doc.name}. Unable to Close for Disabled User")

        if todo and user[0].enabled == 1:
            todo_doc = frappe.get_doc("ToDo", todo[0].name)
            if todo_doc.status == "Open":
                send_reminder = check_follow_up_time(comm.next_action_date, now)
                if send_reminder == 1:
                    send_follow_up_email(comm.user, comm.modified_by, comm.subject, comm.content,
                                         comm.reference_doctype, comm.reference_name)
            else:
                frappe.db.set_value("ToDo", todo[0][0], "status", "Open")
                send_reminder = check_follow_up_time(comm.next_action_date, now)
                if send_reminder == 1:
                    send_follow_up_email(comm.user, comm.modified_by, comm.subject, comm.content,
                                         comm.reference_doctype, comm.reference_name)
        else:
            if user[0].enabled == 1:
                # Create TODO
                todo = frappe.new_doc("ToDo")
                todo.status = "Open"
                todo.priority = "High"
                todo.date = comm.next_action_date.date()
                todo.owner = comm.user
                todo.reference_type = "Communication"
                todo.reference_name = comm.name
                todo.type = comm.communication_subtype
                todo.assigned_by = comm.owner
                todo.description = comm.subject + "\n" + html2text.html2text(comm.content)[0:100] \
                                   + "\n" + comm.reference_doctype + " " + comm.reference_name
                todo.insert()
                send_follow_up_email(comm.user, comm.owner, comm.subject, comm.content, comm.reference_doctype,
                                     comm.reference_name)
    tot_time = int(time.time() - st_time)
    print(f"Total Time Taken = {tot_time} seconds")


def check_follow_up_time(time, now):
    send_reminder = 0
    if 1 < (time_diff_in_hours(time, now)) < 2:
        send_reminder = 1
    return send_reminder


def send_follow_up_email(user, sender, subject, content, ref_doc, ref_name):
    frappe.sendmail(recipients=user, sender=sender, subject="Follow Up for: " + subject,
                    content=content + "\n" + ref_doc + " " + ref_name)
