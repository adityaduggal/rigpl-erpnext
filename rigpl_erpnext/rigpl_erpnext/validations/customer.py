#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from rigpl_erpnext.utils.rigpl_perm import *
import frappe.permissions
import re
from ...utils.sales_utils import compare_cust_pmt_terms


def on_update(doc, method):
    allowed_ids = []
    # Check if Customer Login ID is not Repeated
    if doc.customer_login_id:
        other_login_id = frappe.db.get_value("Customer", {"customer_login_id": doc.customer_login_id,
                                                          "name": ("!=", doc.name)})
        if other_login_id:
            frappe.throw("Customer {0} already linked to User ID {1}".format(other_login_id,
                                                                             doc.customer_login_id))
    # Check for From Lead field and don't allow duplication.
    if doc.lead_name:
        other_lead = frappe.db.get_value("Customer", {"lead_name": doc.lead_name, "name": ("!=", doc.name)})
        if other_lead:
            frappe.throw("Lead {0} already linked to Customer {1}".format(doc.lead_name, other_lead))

    allowed_ids = get_customer_allowed_ids(doc.name)
    for user in allowed_ids:
        role_list = get_user_roles(user)
        role_in_settings, apply_to_all_doctypes, applicable_for = \
            check_role(role_list, "Customer", apply_to_all_doctypes="None")
        if role_in_settings == 1:
            create_new_user_perm(allow="Customer", for_value=doc.name, user=user,
                                 apply_to_all_doctypes=apply_to_all_doctypes, applicable_for=applicable_for)

    con_list = get_dl_parent(dt='Contact', linked_dt='Customer', linked_dn=doc.name)
    for contact in con_list:
        for user in allowed_ids:
            role_list = get_user_roles(user)
            role_in_settings, apply_to_all_doctypes, applicable_for = check_role(role_list, "Contact",
                                                                                 apply_to_all_doctypes="None")
            if role_in_settings == 1:
                create_new_user_perm(allow="Contact", for_value=contact[0], user=user,
                                     apply_to_all_doctypes=apply_to_all_doctypes, applicable_for=applicable_for)

    add_list = get_dl_parent(dt='Address', linked_dt='Customer', linked_dn=doc.name)
    for address in add_list:
        for user in allowed_ids:
            role_list = get_user_roles(user)
            role_in_settings, apply_to_all_doctypes, applicable_for = \
                check_role(role_list, "Address", apply_to_all_doctypes="None")
            if role_in_settings == 1:
                create_new_user_perm(allow="Address", for_value=address[0], user=user,
                                     apply_to_all_doctypes=apply_to_all_doctypes, applicable_for=applicable_for)

    cust_perm_list = get_permission(allow="Customer", for_value=doc.name)
    con_perm_list = []
    add_perm_list = []
    if con_list:
        for contact in con_list:
            con_perm_list_temp = get_permission(allow="Contact", for_value=contact[0])
            con_perm_list.extend(con_perm_list_temp)
    if add_list:
        for add in add_list:
            add_perm_list_temp = get_permission(allow="Address", for_value=add[0])
            add_perm_list.extend(add_perm_list_temp)
    for perm in cust_perm_list:
        if perm[3] not in allowed_ids:
            delete_permission(perm[0])
    for perm in add_perm_list:
        if perm[3] not in allowed_ids:
            delete_permission(perm[0])
    for perm in con_perm_list:
        if perm[3] not in allowed_ids:
            delete_permission(perm[0])


def validate(doc, method):
    compare_cust_pmt_terms(doc)
