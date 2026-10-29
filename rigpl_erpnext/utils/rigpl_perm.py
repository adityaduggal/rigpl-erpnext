# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint


def delete_redundant_custom_permissions():
    custom_perm_parents = frappe.db.sql("""SELECT parent FROM `tabCustom DocPerm` GROUP BY parent
    ORDER BY parent """, as_dict=1)
    print(len(custom_perm_parents))
    for parent in custom_perm_parents:
        try:
            # Try to get doctype
            frappe.get_all(parent.parent)
        except Exception as exp1:
            print(exp1)
            # If doctype does not exist check single doctype
            try:
                frappe.get_single(parent.parent)
            except Exception as exp2:
                print(exp2)
                # If even Single Doctype does not exist delete the Custom Permission
                custom_perms = frappe.db.sql("""SELECT name, parent, parenttype FROM `tabCustom DocPerm`
                    WHERE parent = %s""", parent.parent, as_dict=1)
                for perm in custom_perms:
                    frappe.delete_doc_if_exists("Custom DocPerm", perm.name)
                    print("Deleted Custom Perm for {}: {} with ID: {}".format(perm.parenttype, perm.parent, perm.name))


def create_new_user_perm(user, allow=None, for_value=None, applicable_for=None, apply_to_all_doctypes=None):
    sysmgr = check_system_manager(user)
    enabled_user = frappe.get_value("User", user, "enabled")
    existing_perm = get_permission(allow=allow, for_value=for_value, user=user, \
                                   applicable_for=applicable_for, apply_to_all_doctypes=apply_to_all_doctypes)
    if sysmgr != 1 and enabled_user == 1:
        if not existing_perm:
            # check_settings(allow, for_value, applicable_for, apply_to_all_doctypes)
            new_perm = frappe.new_doc("User Permission")
            new_perm.flags.ignore_permissions = True
            new_perm.user = user
            new_perm.allow = allow
            new_perm.for_value = for_value
            new_perm.apply_to_all_doctypes = apply_to_all_doctypes
            new_perm.applicable_for = applicable_for
            new_perm.insert()
            frappe.msgprint("Added New Permission for {0}: {1} for User: {2}".format(allow, for_value, user))
            print("Added New Permission for " + allow + ": " + for_value + " for User: " + user)
    else:
        if existing_perm:
            for perm in existing_perm:
                frappe.msgprint(str(perm))
                delete_permission(name=perm[0])


def get_permission(name=None, user=None, allow=None, for_value=None, \
                   applicable_for=None, apply_to_all_doctypes=None, deleted=None):
    conditions, values = get_conditions(name=name, user=user, allow=allow, for_value=for_value,
                                        applicable_for=applicable_for)
    if apply_to_all_doctypes == 1:
        conditions += " AND apply_to_all_doctypes = 1"
    elif apply_to_all_doctypes == "None":
        conditions += " AND apply_to_all_doctypes = 0"
    else:
        pass

    query = """SELECT name, allow, for_value, user, applicable_for, 
        apply_to_all_doctypes
        FROM `tabUser Permission` WHERE docstatus = 0 %s""" % (conditions)
    permission_list = frappe.db.sql(query, values, as_list=1)

    return permission_list


def delete_permission(name=None, user=None, allow=None, for_value=None, \
                      applicable_for=None, apply_to_all_doctypes=None):
    permission_list = get_permission(name=name, user=user, allow=allow, \
                                     for_value=for_value, applicable_for=applicable_for, \
                                     apply_to_all_doctypes=apply_to_all_doctypes)
    for perm in permission_list:
        frappe.db.delete("User Permission", {"name": perm[0]})
        frappe.cache().hdel("user_permissions", perm[3])
        frappe.msgprint("Deleted User Permission: {} for User: {} for Doctype: {} \
            for Value: {}".format(perm[0], perm[3], perm[1], perm[2]))

        print('Deleted User Permission: ' + perm[0] + ' for User: ' + perm[3] \
              + ' for Doctype ' + perm[1] + " Value " + perm[2])


def get_docshare(name=None, user=None, share_doctype=None, share_name=None):
    conditions, values = get_conditions(name=name, user=user, share_doctype=share_doctype,
                                        share_name=share_name)
    query = """SELECT name, share_doctype, share_name, user, `read`, `write`, share, everyone, notify_by_email
        FROM `tabDocShare` WHERE docstatus = 0 %s""" % (conditions)
    docshare_list = frappe.db.sql(query, values, as_dict=1)
    return docshare_list


def delete_docshare(name=None, user=None, share_doctype=None, share_name=None):
    docshare_list = get_docshare(name=name, user=user, share_doctype=share_doctype, \
                                 share_name=share_name)
    for docsh in docshare_list:
        frappe.db.delete("DocShare", {"name": docsh.name})
        frappe.msgprint("Deleted DocShare: {} for User: {} for Doctype: {} \
            for Value: {}".format(docsh.name, docsh.user, docsh.share_doctype, \
                                  docsh.share_name))

        print('Deleted DocShare: ' + docsh.name + ' for User: ' + docsh.user \
              + ' for Doctype ' + docsh.share_doctype + " Value " + docsh.share_name)


def check_system_manager(user):
    sysmgr_list = frappe.db.sql("""SELECT name FROM `tabHas Role` 
        WHERE parenttype = 'User' AND parent = %s
        AND role = 'System Manager'""", user, as_list=1)
    if sysmgr_list:
        return 1
    else:
        return 0


def get_dl_parent(dt, linked_dt, linked_dn):
    dl_parent_list = frappe.db.sql("""SELECT parent FROM `tabDynamic Link` 
        WHERE parenttype = %s AND link_doctype = %s
        AND link_name = %s""", (dt, linked_dt, linked_dn), as_list=1)
    if not dl_parent_list:
        dl_parent_list = []
    return dl_parent_list


def get_users(active=0):
    users = frappe.db.sql("""SELECT name FROM `tabUser`
        WHERE enabled = %s""", cint(active), as_list=1)
    return users


def get_employees_allowed_ids(employee):
    allowed_ids = []
    status = frappe.get_value("Employee", employee, "status")
    if status == 'Active':
        user_id = frappe.get_value("Employee", employee, "user_id")
        user_id_perm = frappe.get_value("Employee", employee, "create_user_permission")
        reports_to = frappe.get_value("Employee", employee, "reports_to")
        if user_id is not None and user_id_perm == 1:
            allowed_ids.append(user_id)
        if reports_to:
            allowed_ids.append(reports_to)
    return allowed_ids


def get_department_allowed_ids(dept_doc):
    allowed_ids = []
    if dept_doc.leave_approvers:
        for la in dept_doc.leave_approvers:
            allowed_ids.append(la.approver)
    if dept_doc.expense_approvers:
        for expa in dept_doc.expense_approvers:
            allowed_ids.append(expa.approver)
    return allowed_ids


def get_customer_allowed_ids(customer):
    allowed_ids = []
    customer_doc = frappe.get_doc("Customer", customer)
    for sperson in customer_doc.sales_team:
        if sperson.sales_person:
            s_person_emp = frappe.get_value("Sales Person", sperson.sales_person, "employee")
            if s_person_emp:
                emp_doc = frappe.get_doc("Employee", s_person_emp)
                if emp_doc.status == "Active":
                    if emp_doc.user_id:
                        allowed_ids.extend([emp_doc.user_id])
    if customer_doc.customer_login_id:
        allowed_ids.extend([customer_doc.customer_login_id])
    if customer_doc.default_sales_partner:
        s_partner = frappe.get_doc("Sales Partner", customer_doc.default_sales_partner)
        if s_partner.user:
            user = frappe.get_doc("User", s_partner.user)
            if user.enabled == 1:
                allowed_ids.extend([s_partner.user])
    return allowed_ids


def create_account_perms(acc_doc, user_dict):
    allowed_ids = get_account_allowed_ids(acc_doc.name, user_dict)
    if allowed_ids:
        for user in allowed_ids:
            role_list = get_user_roles(user)
            role_in_settings, apply_to_all_doctypes, applicable_for = \
                check_role(role_list, doctype=acc_doc.doctype, \
                           apply_to_all_doctypes="None")
            if role_in_settings == 1:
                create_new_user_perm(user=user, allow=acc_doc.doctype, \
                                     for_value=acc_doc.name, applicable_for=applicable_for, \
                                     apply_to_all_doctypes=apply_to_all_doctypes)
    delete_extra_account_perms(acc_doc, user_dict)


def delete_extra_account_perms(acc_doc, user_dict):
    allowed_ids = get_account_allowed_ids(acc_doc.name, user_dict)
    acc_perm_list = get_permission(for_value=acc_doc.name)
    settings_list = get_user_perm_settings(allow="Account", \
                                           apply_to_all_values="None", apply_to_all_doctypes="None", \
                                           apply_to_all_roles="None")
    applicable_for_dt_list = []
    for settings in settings_list:
        if settings[4] != 1:
            applicable_for_dt_list.append(settings[3])

    for perm in acc_perm_list:
        if perm[4] not in applicable_for_dt_list:
            delete_permission(name=perm[0])
        if perm[3] in allowed_ids:
            # Check if the user role is there and if not delete
            role_list = get_user_roles(perm[3])
            role_in_settings, apply_to_all_doctypes, applicable_for = \
                check_role(role_list, doctype=acc_doc.doctype, \
                           apply_to_all_doctypes="None")
            if role_in_settings != 1:
                delete_permission(name=perm[0])
        else:
            delete_permission(name=perm[0])


def check_account_perm(acc_doc):
    if acc_doc.users:
        create_account_perms(acc_doc, acc_doc.users)
        if acc_doc.is_group == 1:
            child_acc_list = get_child_acc_list(acc_doc.name)
            for child_acc in child_acc_list:
                child_acc_doc = frappe.get_doc("Account", child_acc[0])
                create_account_perms(child_acc_doc, child_acc_doc.users)
    else:
        delete_extra_account_perms(acc_doc, acc_doc.users)


def copy_users_to_child_accounts(acc_doc):
    if acc_doc.is_group == 1:
        child_acc_list = get_child_acc_list(acc_doc.name)
        if child_acc_list:
            for child_acc in child_acc_list:
                child_acc_doc = frappe.get_doc("Account", child_acc[0])
                copy_grp_user_to_child(acc_doc, child_acc_doc)


def copy_grp_user_to_child(grp_acc_doc, child_acc_doc):
    child_acc_doc.users = []
    user_list = []
    if grp_acc_doc.users:
        for row in grp_acc_doc.users:
            user_dict = {}
            user_dict.setdefault("approver", row.approver)
            user_list.append(user_dict)
        for i in user_list:
            child_acc_doc.append("users", i)
    else:
        child_acc_doc.users = []
    child_acc_doc.save()


def get_child_acc_list(account_name):
    acc_doc = frappe.get_doc("Account", account_name)
    query = """SELECT name FROM `tabAccount` 
        WHERE lft > %s AND rgt < %s"""
    child_acc_list = frappe.db.sql(query, (acc_doc.lft, acc_doc.rgt), as_list=1)
    return child_acc_list


def get_account_allowed_ids(account_name, user_dict):
    allowed_ids = []
    acc_doc = frappe.get_doc("Account", account_name)
    if user_dict:
        for row in user_dict:
            allowed_ids.extend([row.approver])
    return allowed_ids


def get_user_roles(user):
    role_list = frappe.db.sql("""SELECT role FROM `tabHas Role` 
        WHERE parent = %s AND parenttype = 'User'""", user, as_list=1)
    return role_list


def get_user_perm_settings(allow=None, role=None, apply_to_all_roles=None, \
                           apply_to_all_values=None, apply_to_all_doctypes=None):
    # This would check if the user permission needs to be created or not.
    conditions, values = get_conditions(allow_doctype=allow, role=role)
    conditions += get_flag_conditions(apply_to_all_roles=apply_to_all_roles,
                                      apply_to_all_values=apply_to_all_values)

    if apply_to_all_doctypes == 1:
        conditions += " AND apply_to_all_doctypes = 1"
    elif apply_to_all_doctypes == 'None':
        pass
    else:
        conditions += " AND apply_to_all_doctypes = 0"

    query = """SELECT role, allow_doctype, allow_doctype_value, 
        applicable_for_doctype, apply_to_all_doctypes
        FROM `tabUser Permission Rules` WHERE parent = 'User Permission Settings' 
        AND parentfield = 'rules' %s""" \
            % (conditions)
    settings_list = frappe.db.sql(query, values, as_list=1)
    return settings_list


def check_role(role_list, doctype, apply_to_all_doctypes=None):
    role_in_settings = 0
    settings_list = get_user_perm_settings(allow=doctype, \
                                           apply_to_all_values=1, apply_to_all_doctypes=apply_to_all_doctypes)
    if settings_list:
        for set_list in settings_list:
            applicable_for = set_list[3]
            apply_to_all_doctypes = set_list[4]
            for role in role_list:
                if role[0] == set_list[0]:
                    role_in_settings = 1
    else:
        role_in_settings = 0
        apply_to_all_doctypes = 0
        applicable_for = 0
    return role_in_settings, apply_to_all_doctypes, applicable_for


def get_usershare_settings(document_type=None, role=None, apply_to_all_roles=None, \
                           apply_to_all_values=None, document_name=None):
    # This would check if the user permission needs to be created or not.
    conditions, values = get_conditions(document_type=document_type, document_name=document_name,
                                        role=role)
    conditions += get_flag_conditions(apply_to_all_roles=apply_to_all_roles,
                                      apply_to_all_values=apply_to_all_values)

    query = """SELECT name, role, apply_to_all_roles, document_type, document_name, 
        apply_to_all_values, read_access, write_access, share_access, notify_by_email
        FROM `tabUser Share Rules` WHERE parent = 'User Share Settings' 
        AND parentfield = 'rules' %s""" \
            % (conditions)
    settings_dict = frappe.db.sql(query, values, as_dict=1)
    return settings_dict


def check_role_usershare(role_list, doctype):
    role_in_settings = 0
    settings_dict = get_usershare_settings(document_type=doctype, \
                                           apply_to_all_values=1)
    if settings_dict:
        for set_dict in settings_dict:
            read_access = set_dict.read_access
            write_access = set_dict.write_access
            share_access = set_dict.share_access
            notify_by_email = set_dict.notify_by_email
            document_type = set_dict.document_type
            for role in role_list:
                if role[0] == set_dict.role:
                    role_in_settings = 1
    else:
        role_in_settings = 0
        read_access = 0
        write_access = 0
        share_access = 0
        notify_by_email = 0

    return role_in_settings, write_access, share_access, notify_by_email


def get_shared(name=None, user=None, document_type=None, document_name=None):
    conditions, values = get_conditions(name=name, user=user, share_doctype=document_type,
                                        share_name=document_name)

    query = """SELECT name, user, share_doctype, share_name, `read`, `write`,
        `share`, `everyone`, notify_by_email
        FROM `tabDocShare` WHERE docstatus = 0 %s""" % (conditions)
    share_dict = frappe.db.sql(query, values, as_dict=1)
    return share_dict


def get_conditions(**fields):
    """
    Returns (" AND field = %(field)s ...", values) for the fields with a value. Only fixed column
    names go in the SQL, the values are parameters.
    """
    values = {field: value for field, value in fields.items() if value}
    conditions = "".join(" AND {0} = %({0})s".format(field) for field in values)
    return conditions, values


def get_flag_conditions(**flags):
    """1 checks the flag, "None" skips it and any other value checks that it is 0"""
    conditions = ""
    for field, value in flags.items():
        if value == 1:
            conditions += " AND {} = 1".format(field)
        elif value != "None":
            conditions += " AND {} = 0".format(field)
    return conditions
