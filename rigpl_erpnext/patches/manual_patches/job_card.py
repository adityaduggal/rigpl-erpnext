# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import time
from ...utils.job_card_utils import get_job_card_process_sno


# This Patch would update the Serial No and Final Op for Job Card
# This Patch also updates the Transfer entry field in BOM templates and Process Sheet and Process Job Cards
def execute():
    st_time = time.time()
    all_bt = frappe.db.sql("""SELECT name FROM `tabBOM Template RIGPL`""", as_dict=1)
    for bt in all_bt:
        bt_doc = frappe.get_doc("BOM Template RIGPL", bt.name)
        for op in bt_doc.operations:
            if op.source_warehouse and op.target_warehouse and op.transfer_entry != 1:
                op.transfer_entry = 1
                op.save()
                print(f"{bt_doc.name} Updated for {op.operation} and Updated as Transfer Entry")
    frappe.db.commit()
    bt_time = int(time.time() - st_time)
    print(f"Total Time for BOM Templates {bt_time} seconds")
    ps_st_time = time.time()
    all_ps = frappe.db.sql("""SELECT name FROM `tabProcess Sheet` WHERE docstatus < 2 ORDER BY name""", as_dict=1)
    for ps in all_ps:
        ps_doc = frappe.get_doc("Process Sheet", ps.name)
        for op in ps_doc.operations:
            if op.source_warehouse and op.source_warehouse != "":
                if op.target_warehouse:
                    if op.transfer_entry != 1:
                        op.transfer_entry = 1
                        op.save()
                        print(f"{ps_doc.name} Updated for {op.operation} and Updated as Transfer Entry")
            else:
                if op.transfer_entry == 1:
                    op.transfer_entry = 0
                    print(f"{ps_doc.name} Updated for {op.operation} and Removed as Transfer Entry")
    frappe.db.commit()
    ps_time = int(time.time() - ps_st_time)
    print(f"Total Time for Process Sheets {ps_time} seconds")
    jc_st_time = time.time()
    all_jc = frappe.db.sql("""SELECT name, docstatus, production_item FROM `tabProcess Job Card RIGPL` 
    WHERE docstatus < 2 ORDER BY name DESC""", as_dict=1)
    jc_updated = 0
    for jc in all_jc:
        # Update Job Card Operation Serial Number
        jc_doc = frappe.get_doc("Process Job Card RIGPL", jc.name)
        op_doc = frappe.get_doc("BOM Operation", jc_doc.operation_id)
        if jc_doc.transfer_entry != op_doc.transfer_entry:
            frappe.db.set_value(jc_doc.doctype, jc_doc.name, "transfer_entry", op_doc.transfer_entry)
            jc_updated += 1
            print(f"Updated {jc.name} for Transfer Entry")
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
    jc_time = int(time.time() - jc_st_time)
    print(f"Total Time for Job Cards {jc_time} seconds")
    wrong_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus < 2 AND transfer_entry = 1
    AND s_warehouse IS NULL""", as_dict=1)
    sno = 1
    for jc in wrong_jc:
        print(f"{sno}. No Source Warehouse mentioned in {jc.name}")
        sno += 1
    tot_time = int(time.time() - st_time)
    print(f"Total Time for All Processes {tot_time} seconds")


def check_for_multiple_po_for_same_jc():
    all_po_with_jc = frappe.db.sql("""SELECT po.name as po, poi.reference_dn as jc
    FROM `tabPurchase Order` po, `tabPurchase Order Item` poi WHERE poi.parent = po.name AND po.docstatus = 1
    AND poi.reference_dt = "Process Job Card RIGPL" AND poi.reference_dn IS NOT NULL
    ORDER BY poi.reference_dn, po.name""", as_dict=1)
    for jc in all_po_with_jc:
        print(f"Checking for JC# {jc.jc}")
        other_po = frappe.db.sql("""SELECT po.name FROM `tabPurchase Order` po, `tabPurchase Order Item` poi
        WHERE poi.parent = po.name AND po.docstatus=1 AND poi.reference_dt = 'Process Job Card RIGPL' AND
        poi.reference_dn = '%s' AND po.name != '%s' """ % (jc.jc, jc.po), as_dict=1)
        if other_po:
            print(f"OTHER PO# = {other_po} FOR JC# = {jc.name}")
        else:
            print(f"No Other PO found for JC# {jc.jc}")
