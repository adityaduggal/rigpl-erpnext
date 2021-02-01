# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from frappe.utils import today, flt
from ..doctype.process_sheet.process_sheet import update_priority_psd
from ...utils.process_sheet_utils import make_jc_for_process_sheet, update_process_sheet_quantities, \
    update_process_sheet_operations
from ...utils.manufacturing_utils import get_qty_to_manufacture, get_quantities_for_item

from frappe.utils.background_jobs import enqueue


def enqueue_process_sheet_update():
    enqueue(execute, queue="long", timeout=1500)


def execute():
    st_time = time.time()
    create_new_process_sheets()
    update_process_sheet_priority()
    frappe.db.commit()
    # update_process_sheet_status()
    total_time = int(time.time() - st_time)
    print(f"Total Time taken = {total_time} seconds")


def update_process_sheet_priority():
    st_time = time.time()
    count = 0
    ps_list = frappe.db.sql("""SELECT name, docstatus FROM `tabProcess Sheet` WHERE docstatus < 2 AND status != 'Completed' 
    AND status != 'Short Closed' AND status != 'Stopped' ORDER BY creation ASC""", as_dict=1)
    for ps in ps_list:
        psd = frappe.get_doc("Process Sheet", ps.name)
        old_priority = psd.priority
        itd = frappe.get_doc("Item", psd.production_item)
        update_priority_psd(psd, itd, backend=1)
        if old_priority != psd.priority:
            count += 1
        if psd.docstatus == 0 and psd.status != "Draft":
            frappe.db.set_value("Process Sheet", psd.name, "status", "Draft")
            print(f"Updated Status for {psd.name} to Draft")
        elif psd.docstatus == 1 and psd.status == "Draft":
            frappe.db.set_value("Process Sheet", psd.name, "status", "Submitted")
            print(f"Updated Status for {psd.name} to Submitted")
    end_time = int(time.time() - st_time)
    print(f"Total No of Process Sheets where Priority has been Updated = {count}")
    print(f"Total Time for Updating Priority = {end_time} seconds")


def create_new_process_sheets():
    st_time = time.time()
    value = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "auto_process_sheet_value"))
    if value == 0:
        value = 10000
    # Check items in Warehouses in Production without Job Cards
    it_dict = frappe.db.sql("""SELECT it.name, it.valuation_rate AS vrate, it_rol.warehouse_reorder_level AS wh_rol,
    (it.valuation_rate * it_rol.warehouse_reorder_level) AS vr_rol
    FROM `tabItem` it LEFT JOIN `tabItem Reorder` it_rol ON it_rol.parent = it.name AND it_rol.parenttype = 'Item' 
    WHERE it.disabled = 0 AND it.include_item_in_manufacturing = 1 AND it.has_variants = 0 AND it.variant_of IS NOT NULL 
    ORDER BY vr_rol DESC, vrate DESC, wh_rol DESC, name ASC""", as_dict=1)
    print(f"Total Items Being Considered for Auto Process Sheet = {len(it_dict)}")
    created = 0
    err_it = []
    for it in it_dict:
        vr_rol = flt(it.vrate) * flt(it.wh_rol)
        # print(f"Considering {it.name} ROL= {it.wh_rol} VRATE = {it.vrate} VR*ROL {it.vr_rol}")
        it_doc = frappe.get_doc("Item", it.name)
        qty = get_qty_to_manufacture(it_doc)
        qty_dict = get_quantities_for_item(it_doc)
        value_for_manf = qty * qty_dict["valuation_rate"]
        if value_for_manf >= value:
            exiting_ps = frappe.db.sql("""SELECT name FROM `tabProcess Sheet` WHERE docstatus=0 
            AND production_item= '%s'""" % it.name, as_dict=1)
            if exiting_ps:
                ex_ps = frappe.get_doc("Process Sheet", exiting_ps[0].name)
                if ex_ps.quantity != qty:
                    old_qty = ex_ps.quantity
                    ex_ps.quantity = qty
                    print(f"Updated {ex_ps.name} Changed Quantity from {old_qty} to {qty} for {it.name} "
                          f"VR*ROL = {vr_rol}")
                    try:
                        ex_ps.save()
                    except:
                        frappe.db.set_value("Process Sheet", ex_ps.name, "quantity", qty)
                        print(f"Updated {ex_ps.name} Changed Quantity from {old_qty} to {qty} for {it.name} "
                              f"VR*ROL = {vr_rol}")
            else:
                try:
                    ps = frappe.new_doc("Process Sheet")
                    ps.production_item = it.name
                    ps.date = today()
                    ps.quantity = qty
                    ps.status = "Draft"
                    ps.insert()
                    frappe.db.commit()
                    print(f"Created {ps.name} for {it.name} for Qty= {qty} VR*ROL = {vr_rol}")
                    created += 1
                except:
                    err_it.append(it.name)
                    print(f"Error Encountered while Creating Process Sheet for {it.name} Qty = {qty} "
                          f"VR*ROL = {vr_rol}")
    print(f"List of Items where New Process Sheet cannot be Made \n {err_it}")
    it_time = int(time.time() - st_time)
    print(f"Total Process Sheets Created = {created}")
    print(f"Total Time for Creation of Process Sheets = {it_time} seconds")


def update_process_sheet_status():
    st_time = time.time()
    ps_count = 0
    ps_dict = frappe.db.sql("""SELECT ps.name, ps.status, ps.priority, pso.idx, pso.name AS op_id, 
    pso.status AS op_status FROM `tabProcess Sheet` ps, `tabBOM Operation` pso
    WHERE ps.docstatus = 1 AND pso.status != 'Completed' AND pso.status != 'Stopped' AND pso.status != 'Short Closed'
    AND pso.status != 'Obsolete' AND pso.parent = ps.name AND pso.parenttype = 'Process Sheet'
    ORDER BY name""", as_dict=1)
    print(f"Total No of Process Sheet Processes Being Considered = {len(ps_dict)}")
    for i in range(len(ps_dict)):
        print(ps_count)
        if i > 0:
            if ps_dict[i].name != ps_dict[i-1].name:
                ps_count = process_sheet_status(ps_dict[i].name, st_time, ps_count)
        else:
            ps_count = process_sheet_status(ps_dict[i].name, st_time, ps_count)
    end_time = time.time()
    tot_ps_time = round(end_time - st_time)
    print(f"Total Process Sheet Status Updated = {ps_count}")
    print(f"Total Time Taken for Process Sheets is {tot_ps_time} seconds")


def process_sheet_status(ps_name, st_time, ps_count):
    print(f"Processing {ps_name}. Time Elapsed = {int(time.time() - st_time)} seconds")
    ps_doc = frappe.get_doc("Process Sheet", ps_name)
    make_jc_for_process_sheet(ps_doc)
    update_process_sheet_quantities(ps_doc)
    for op in ps_doc.operations:
        update_process_sheet_operations(ps_doc.name, op.name)
    if ps_doc.short_closed_qty > 0:
        if ps_doc.produced_qty < ps_doc.quantity:
            if ps_doc.status != "Short Closed":
                ps_doc.status = "Short Closed"
                print("Short Closed {}".format(ps_doc.name))
        else:
            if ps_doc.status != "Completed":
                ps_doc.status = "Completed"
                print("Completed {}".format(ps_doc.name))
    elif ps_doc.quantity <= ps_doc.produced_qty:
        if ps_doc.status != "Completed":
            ps_count += 1
            ps_doc.status = "Completed"
            print("Completed {}".format(ps_doc.name))
    else:
        for op in ps_doc.operations:
            if op.completed_qty > 0:
                if ps_doc.status != "In Progress" and ps_doc.status != "Stopped":
                    ps_count += 1
                    ps_doc.status = "In Progress"
                    print("In Progress Status set for {}".format(ps_doc.name))
    ps_doc.save()
    return ps_count
