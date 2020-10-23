# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def execute():
    all_jc = frappe.db.sql("""SELECT name, docstatus, production_item FROM `tabProcess Job Card RIGPL`""", as_dict=1)
    for jc in all_jc:
        it_uom = frappe.get_value("Item", jc.production_item, "stock_uom")
        # Update item UOM in all JC
        frappe.db.set_value("Process Job Card RIGPL", jc.name, "uom", it_uom)
        if jc.docstatus == 1:
            # Update STE for Submitted JC
            query = """SELECT name FROM `tabStock Entry` WHERE remarks LIKE '%s'"""% ('%' + jc.name)
            ste_dict = frappe.db.sql(query, as_dict=1)
            if ste_dict:
                for ste in ste_dict:
                    frappe.set_value("Stock Entry", ste.name, "process_job_card", jc.name)
