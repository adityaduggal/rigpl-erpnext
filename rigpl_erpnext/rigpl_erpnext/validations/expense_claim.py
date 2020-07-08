# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
    doc.department = frappe.get_value("Employee", doc.employee, "department")
