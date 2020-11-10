# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from ...utils.job_card_utils import get_job_card_process_sno


def execute():
    all_jc = frappe.db.sql("""SELECT name, docstatus, production_item FROM `tabProcess Job Card RIGPL`""", as_dict=1)
    for jc in all_jc:
        print(f"Processing {jc.name}")
        # Update Job Card Operation Serial Number
        jc_doc = frappe.get_doc("Process Job Card RIGPL", jc.name)
        it_uom = frappe.get_value("Item", jc.production_item, "stock_uom")
        op_sno, final = get_job_card_process_sno(jc_doc)
        if op_sno != jc_doc.operation_serial_no or final != jc_doc.final_operation:
            print(f"For {jc.name} Updating Serial No and Final Op")
            frappe.db.set_value(jc_doc.doctype, jc.name, "operation_serial_no", op_sno)
            frappe.db.set_value(jc_doc.doctype, jc.name, "final_operation", final)
        # Update item UOM in all JC
        if it_uom != jc_doc.uom:
            frappe.db.set_value("Process Job Card RIGPL", jc.name, "uom", it_uom)
        if jc.docstatus == 1:
            # Update STE for Submitted JC
            query = """SELECT name FROM `tabStock Entry` WHERE process_job_card IS NULL 
            AND remarks LIKE '%s'"""% ('%' + jc.name)
            ste_dict = frappe.db.sql(query, as_dict=1)
            if ste_dict:
                for ste in ste_dict:
                    frappe.set_value("Stock Entry", ste.name, "process_job_card", jc.name)
