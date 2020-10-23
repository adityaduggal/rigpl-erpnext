# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def execute():
    submitted_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus = 1""", as_dict=1)
    for jc in submitted_jc:
        query = """SELECT name FROM `tabStock Entry` WHERE remarks LIKE '%s'"""% ('%' + jc.name)
        ste_dict = frappe.db.sql(query, as_dict=1)
        if ste_dict:
            for ste in ste_dict:
                frappe.set_value("Stock Entry", ste.name, "process_job_card", jc.name)
