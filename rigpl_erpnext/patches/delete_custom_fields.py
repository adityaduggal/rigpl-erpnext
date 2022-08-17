# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def execute():
    # Deletes custom fields from Custom Field Table based on Dictionary
    custom_field_list = [{"dt": "Attendance", "fieldname": "shift"},
                         {"dt": "Lead", "fieldname": "designation"}
                         ]
    for fld in custom_field_list:
        custom_field = frappe.db.get_value("Custom Field", fld)
        if custom_field:
            frappe.delete_doc("Custom Field", custom_field)
            print(f"Deleted Custom Field: {custom_field} with Filters: {fld}")
