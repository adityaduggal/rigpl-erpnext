# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from frappe.utils import now
from rigpl_erpnext.utils.batch_write_utils import bulk_insert_rows, clear_document_cache
from rigpl_erpnext.utils.rigpl_perm import *

# RIGPL Settings > Department Approvers. The tables that get a copy of leave_approvers (#238).
APPROVER_MODES = ("Leave, Expense and Shift Same", "Leave and Shift Same, Expense Different", "All Different")
COPY_TABLES = {
    APPROVER_MODES[0]: ("expense_approvers", "shift_request_approver"),
    APPROVER_MODES[1]: ("shift_request_approver",),
    APPROVER_MODES[2]: (),
}


def validate(doc, method):
    copy_approvers(doc, get_approver_mode())
    allowed_ids = get_department_allowed_ids(doc)
    for user in allowed_ids:
        role_list = get_user_roles(user)
        role_in_settings, apply_to_all_doctypes, applicable_for = check_role(role_list, doc.doctype,
                                                                             apply_to_all_doctypes="None")
        if role_in_settings == 1:
            create_new_user_perm(allow=doc.doctype, for_value=doc.name, user=user,
                                 apply_to_all_doctypes=apply_to_all_doctypes, applicable_for=applicable_for)
    dept_perm_list = get_permission(allow=doc.doctype, for_value=doc.name)
    for perm in dept_perm_list:
        if perm[3] not in allowed_ids:
            delete_permission(perm[0])


def get_approver_mode():
    return frappe.db.get_single_value("RIGPL Settings", "department_approver_mode") or APPROVER_MODES[0]


def copy_approvers(doc, mode):
    for table in COPY_TABLES.get(mode, ()):
        doc.set(table, [{"approver": row.approver} for row in doc.leave_approvers])


def sync_all_department_approvers(mode=APPROVER_MODES[0]):
    """Patch: copies leave_approvers of all Departments like copy_approvers, without a save of each Department.
    The mode is an argument: the patch runs before the schema sync adds the RIGPL Settings field."""
    tables = COPY_TABLES[mode]
    if not tables:
        return
    leave = frappe.get_all("Department Approver", filters={"parenttype": "Department",
        "parentfield": "leave_approvers"}, fields=["parent", "approver", "idx"], order_by="parent, idx")
    frappe.db.delete("Department Approver", {"parenttype": "Department", "parentfield": ("in", tables)})
    timestamp, user = now(), frappe.session.user
    rows = [(frappe.generate_hash(length=10), timestamp, timestamp, user, user, row.parent, "Department", table,
        row.idx, row.approver) for table in tables for row in leave]
    bulk_insert_rows("Department Approver", ("name", "creation", "modified", "owner", "modified_by", "parent",
        "parenttype", "parentfield", "idx", "approver"), rows)
    clear_document_cache("Department", {row.parent for row in leave})
