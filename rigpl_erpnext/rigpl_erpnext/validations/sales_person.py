# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def validate(doc, method):
    if not doc.employee:
        frappe.throw("Employee is Mandatory for Sales Person")
    else:
        emp_doc = frappe.get_doc("Employee", doc.employee)
        if not emp_doc.user_id:
            frappe.throw(f"{frappe.get_desk_link('Employee', doc.employee)} does not have a ERP User ID hence "
                         f"cannot be linked to the Sales Person {doc.name}")
        else:
            doc.email_id = emp_doc.user_id
