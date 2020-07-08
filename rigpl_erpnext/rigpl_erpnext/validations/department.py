# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from rigpl_erpnext.utils.rigpl_perm import *


def validate(doc, method):
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
