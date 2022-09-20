#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-

import frappe


def validate(doc, method):
    """
    Validation for Leave Policy which are not in standard ERPNext
    1. Leave Policy should deny Leave Without Pay since there is no point
    in having a policy for leave without pay allocation
    """
    for row in doc.leave_policy_details:
        if row.leave_type:
            ldt = frappe.get_doc("Leave Type", row.leave_type)
            if ldt.is_lwp == 1:
                frappe.throw(
                    f"{frappe.get_desk_link(ldt.doctype, ldt.name)} is Leave Without Pay \
                    and hence not allowed in Leave Policy"
                )
