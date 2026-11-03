# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
    doc.department = frappe.get_value("Employee", doc.employee, "department")
    # ERPNext makes the leave attendance on submit, so no attendance may exist for these days
    att = frappe.get_all("Attendance", filters={"docstatus": 1, "employee": doc.employee,
        "attendance_date": ("between", [doc.from_date, doc.to_date])}, limit=1)
    if att:
        frappe.throw(
            "Employee: {0} already has attendance between {1} and {2}".format(doc.employee_name,
                                                                              doc.from_date, doc.to_date))
