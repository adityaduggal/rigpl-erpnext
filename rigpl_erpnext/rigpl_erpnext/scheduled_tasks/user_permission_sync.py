# -*- coding: utf-8 -*-
#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
Hourly sync of the User Permissions with the rules in User Permission Settings (#148). It replaces
the hourly create_defaults and the daily check_permission_exist, which had 2 different rule sets
and kept adding and deleting the same permissions.

All the inputs are read once. get_changes works out in memory which permissions to insert and
which to delete, and only those rows are written. A permission that a rule asks for is never
deleted.
"""
from __future__ import unicode_literals
import time
import frappe
from frappe.utils import cint, cstr
from ...utils.item_attribute_utils import chunks
from .process_sheet_update import run_write

UP_DOCTYPE = "User Permission"
UP_FIELDS = ["name", "user", "allow", "for_value", "applicable_for", "apply_to_all_doctypes"]
RULE_FIELDS = ["role", "apply_to_all_roles", "allow_doctype", "allow_doctype_value",
    "apply_to_all_values", "applicable_for_doctype", "apply_to_all_doctypes"]
NO_PERMISSION_USERS = ("Administrator", "Guest")
PURGE_DELETED_DOCTYPES = ["User Permission", "Error Log", "Email Group Member", "Version"]


def execute():
    st_time = time.time()
    clean_orphan_rows()
    sync_user_permissions()
    frappe.db.delete("Deleted Document", {"deleted_doctype": ("in", PURGE_DELETED_DOCTYPES)})
    print(f"User Permission Sync done in {int(time.time() - st_time)} seconds")


def clean_orphan_rows():
    """Deletes the Address Dynamic Links and the Customer Sales Team rows whose parent is gone"""
    for child, parenttype in (("Dynamic Link", "Address"), ("Sales Team", "Customer")):
        table, parent = frappe.qb.DocType(child), frappe.qb.DocType(parenttype)
        (
            frappe.qb.from_(table).delete()
            .where(table.parenttype == parenttype)
            .where(table.parent.notin(frappe.qb.from_(parent).select(parent.name)))
            .run()
        )


def sync_user_permissions(dry_run=False):
    """
    Inserts the missing and deletes the extra User Permissions. Returns (to_insert, to_delete),
    and with dry_run=True writes nothing.
    """
    to_insert, to_delete = get_changes(load_context())
    if dry_run:
        return to_insert, to_delete
    inserted = 0
    for key in to_insert:
        user, allow, for_value, applicable_for, apply_to_all_doctypes = key
        doc = frappe.get_doc({
            "doctype": UP_DOCTYPE, "user": user, "allow": allow, "for_value": for_value,
            "applicable_for": applicable_for or None, "apply_to_all_doctypes": apply_to_all_doctypes,
        })
        if run_write("user_perm_sync", lambda: doc.insert(ignore_permissions=True),
                f"User Permission Sync: {allow} {for_value} for {user} not added"):
            inserted += 1
    for chunk in chunks([perm.name for perm in to_delete]):
        frappe.db.delete(UP_DOCTYPE, {"name": ("in", chunk)})
    for user in {perm.user for perm in to_delete}:
        frappe.cache().hdel("user_permissions", user)
    print(f"User Permissions added: {inserted} of {len(to_insert)}, deleted: {len(to_delete)}")
    return to_insert, to_delete


def load_context():
    ctx = frappe._dict()
    ctx.enabled = {name for name, enabled in frappe.get_all("User", fields=["name", "enabled"],
        as_list=True) if enabled}
    ctx.roles = {}
    for user, role in frappe.get_all("Has Role", filters={"parenttype": "User"},
            fields=["parent", "role"], as_list=True):
        ctx.roles.setdefault(user, set()).add(role)
    ctx.rules = frappe.get_all("User Permission Rules", filters={"parent": "User Permission Settings",
        "parentfield": "rules"}, fields=RULE_FIELDS, order_by="idx")
    ctx.perms = frappe.get_all(UP_DOCTYPE, fields=UP_FIELDS, order_by="name")
    ctx.employees = frappe.get_all("Employee", fields=["name", "status", "user_id",
        "create_user_permission"])
    ctx.approvers = {}
    for account, approver in frappe.get_all("Department Approver", filters={"parenttype": "Account",
            "parentfield": "users"}, fields=["parent", "approver"], as_list=True):
        ctx.approvers.setdefault(account, set()).add(approver)
    return ctx


def get_changes(ctx):
    """
    Returns ([keys to insert], [User Permission rows to delete]). A key is (user, allow,
    for_value, applicable_for, apply_to_all_doctypes), like the duplicate check of User Permission.
    """
    eligible = {user for user in ctx.enabled if user not in NO_PERMISSION_USERS
        and "System Manager" not in ctx.roles.get(user, ())}
    wanted = get_wanted(ctx, eligible)
    existing = {perm_key(perm): perm for perm in ctx.perms}
    all_dt = {key[:3] for key in list(wanted) + list(existing) if key[4] == 1}
    # A permission for all doctypes covers the same value for one doctype
    wanted = [key for key in wanted if not (key[4] == 0 and key[:3] in all_dt)]
    checks = frappe._dict(
        eligible=eligible, all_dt=all_dt,
        left_employees={emp.name for emp in ctx.employees if emp.status == "Left"},
        account_for={cstr(rule.applicable_for_doctype) for rule in ctx.rules
            if rule.allow_doctype == "Account" and cint(rule.apply_to_all_doctypes) != 1},
    )
    to_insert = [key for key in wanted if key not in existing]
    wanted = set(wanted)
    to_delete = [perm for key, perm in existing.items() if key not in wanted and is_extra(perm, ctx, checks)]
    return to_insert, to_delete


def get_wanted(ctx, eligible):
    """Returns the keys that the rules, the Employees and the Account approvers ask for, in order"""
    wanted = {}
    for user in sorted(eligible):
        roles = ctx.roles.get(user, set())
        for rule in ctx.rules:
            if rule.apply_to_all_values or not rule.allow_doctype_value:
                continue
            if rule.apply_to_all_roles or rule.role in roles:
                wanted[rule_key(user, rule, rule.allow_doctype_value)] = 1
        emp_rule = get_role_rule(ctx.rules, roles, "Employee")
        if emp_rule:
            for emp in ctx.employees:
                if emp.status == "Active" and emp.user_id == user and emp.create_user_permission == 1:
                    wanted[rule_key(user, emp_rule, emp.name)] = 1
        acc_rule = get_role_rule(ctx.rules, roles, "Account")
        if acc_rule:
            for account in sorted(ctx.approvers):
                if user in ctx.approvers[account]:
                    wanted[rule_key(user, acc_rule, account)] = 1
    return wanted


def is_extra(perm, ctx, checks):
    """True when an existing permission that no rule asks for has to go, by the rules of the old jobs"""
    if perm.user not in checks.eligible:
        return True
    roles = ctx.roles.get(perm.user, set())
    all_doctypes = cint(perm.apply_to_all_doctypes)
    if all_doctypes == 0 and (perm.user, perm.allow, perm.for_value) in checks.all_dt:
        return True
    if all_doctypes == 1 and not get_role_rule(ctx.rules, roles, perm.allow, apply_to_all_doctypes=1):
        return True
    if perm.allow == "Employee" and perm.for_value in checks.left_employees:
        return True
    if perm.allow == "Account":
        return (cstr(perm.applicable_for) not in checks.account_for
            or perm.user not in ctx.approvers.get(perm.for_value, ())
            or not get_role_rule(ctx.rules, roles, "Account"))
    return False

def get_role_rule(rules, roles, doctype, apply_to_all_doctypes=None):
    """
    Returns the rule whose applicable_for and apply_to_all_doctypes apply when the user has a role
    in the "all values" rules of the doctype, else None. Like check_role, that is the last rule.
    """
    matches = [rule for rule in rules if rule.allow_doctype == doctype and rule.apply_to_all_values
        and not rule.apply_to_all_roles
        and (apply_to_all_doctypes is None or cint(rule.apply_to_all_doctypes) == apply_to_all_doctypes)]
    if any(rule.role in roles for rule in matches):
        return matches[-1]
    return None


def rule_key(user, rule, for_value):
    return (user, rule.allow_doctype, for_value, cstr(rule.applicable_for_doctype),
        cint(rule.apply_to_all_doctypes))


def perm_key(perm):
    return (perm.user, perm.allow, perm.for_value, cstr(perm.applicable_for),
        cint(perm.apply_to_all_doctypes))
