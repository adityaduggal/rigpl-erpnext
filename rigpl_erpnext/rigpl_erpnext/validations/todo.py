# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import get_datetime
from rigpl_erpnext.rigpl_erpnext.doctype.daily_call.daily_call import check_date_time_diff
from rigpl_erpnext.utils.follow_up_utils import end_follow_ups

CLOSED_STATUSES = ("Closed", "Cancelled")


def validate(doc, method):
    if doc.reference_type != 'Communication':
        return
    if not doc.reference_name:
        frappe.throw('Reference Name is Mandatory for {} Reference Type'.format(doc.reference_type))
    if doc.status in CLOSED_STATUSES and doc.has_value_changed("status"):
        # Closed without a new date (list edit, assignment removed): no more follow-up. A Replan
        # through close_follow_up sets the new date after this runs, so it is not undone.
        end_follow_ups([doc.reference_name])


@frappe.whitelist()
def close_follow_up(todo, status="Closed", next_action_date=None):
    """
    Closes a follow-up ToDo. With `next_action_date` (Replan) the Communication is due again on
    that date and the hourly job makes a new ToDo then. Without it (No Follow Up), the follow-up ends.
    """
    if not isinstance(todo, str):
        frappe.throw("ToDo must be a name")
    doc = frappe.get_doc("ToDo", todo)
    if doc.reference_type != "Communication":
        frappe.throw("ToDo {} is not for a Communication".format(doc.name))
    if status not in CLOSED_STATUSES:
        frappe.throw("Status must be Closed or Cancelled")
    if frappe.session.user not in (doc.owner, doc.assigned_by) and "System Manager" not in frappe.get_roles():
        frappe.throw("Only the user or the assigner of the ToDo can close it", frappe.PermissionError)
    if next_action_date:
        check_date_time_diff(next_action_date, hours_diff=1, type_of_check='time', name_of_field='Next Action')
    # validate ends the follow-up, so a replan sets the new date after the save
    doc.status = status
    doc.save(ignore_permissions=True)
    if next_action_date:
        frappe.db.set_value("Communication", doc.reference_name,
                            {"follow_up": 1, "next_action_date": get_datetime(next_action_date)})
