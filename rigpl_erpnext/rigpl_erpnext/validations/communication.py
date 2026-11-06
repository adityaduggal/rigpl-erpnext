# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from rigpl_erpnext.rigpl_erpnext.doctype.daily_call.daily_call import check_date_time_diff
from rigpl_erpnext.utils.follow_up_utils import end_follow_ups, end_party_follow_ups


def validate(doc, method):
    if not doc.flags.from_daily_call and not doc.is_new():
        keep_daily_call_values(doc)
    if doc.follow_up == 1:
        if not doc.next_action_date:
            frappe.throw('Next Action Date is Mandatory for Follow Up Communication')
        elif doc.has_value_changed("next_action_date") or doc.has_value_changed("follow_up"):
            check_date_time_diff(doc.next_action_date, hours_diff=1, type_of_check='time', name_of_field='Next Action')


def keep_daily_call_values(doc):
    """A Communication made by a Daily Call keeps the values of its DCR row."""
    row = frappe.db.get_value("Daily Call Details", {"communication": doc.name},
        ["details", "document", "document_name", "type_of_communication", "communication_date"], as_dict=1)
    if not row:
        return
    doc.content = row.details
    doc.reference_doctype = row.document
    doc.reference_name = row.document_name
    doc.communication_medium = row.type_of_communication
    doc.communication_date = row.communication_date


def after_insert(doc, method):
    # The latest call to a party ends its older follow-ups of all users. A Daily Call does this
    # once for all its rows.
    if doc.flags.from_daily_call or doc.communication_type != "Communication" or \
            not (doc.reference_doctype and doc.reference_name):
        return
    end_party_follow_ups([(doc.reference_doctype, doc.reference_name)], exclude=[doc.name])


@frappe.whitelist()
def end_follow_up(communication):
    """Ends the follow-up of a Communication and closes its Open ToDos."""
    if not isinstance(communication, str):
        frappe.throw("Communication must be a name")
    doc = frappe.get_doc("Communication", communication)
    doc.check_permission("write")
    end_follow_ups([doc.name])
