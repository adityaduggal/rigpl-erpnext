# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from operator import itemgetter
from frappe.utils import today, flt
from ..doctype.process_sheet.process_sheet import update_priority_psd
from ...utils.process_sheet_utils import update_process_sheet_quantities, update_process_sheet_operations, \
    get_pend_psop, stop_ps_operation, get_actual_qty_before_process_in_ps
from ...utils.manufacturing_utils import get_qty_to_manufacture, get_quantities_for_item
from ...utils.job_card_utils import check_existing_job_card, create_job_card
from frappe.utils.background_jobs import enqueue


def enqueue_process_sheet_update():
    enqueue(execute, queue="long", timeout=1500, is_async=False)


def execute():
    st_time = time.time()
    create_new_process_sheets()
    consolidate_transfer_operations()
    update_process_sheet_priority()
    frappe.db.commit()
    # update_process_sheet_status()
    total_time = int(time.time() - st_time)
    print(f"Total Time taken = {total_time} seconds")


def consolidate_transfer_operations():
    st_time = time.time()
    pend_ps_ops = get_pend_psop(tf_ent=1)
    done_ops = []
    done_op_dict = frappe._dict({})
    sno, stopped_ops, changed_ops, unchanged_ops, tot_changes, create_nos = 0, 0, 0, 0, 0, 0
    tot_pen_ops = len(pend_ps_ops)
    print(f"Total Pending Operations to be Analysed = {tot_pen_ops}")
    if pend_ps_ops:
        for op in pend_ps_ops:
            sno += 1
            # print(f"Processing Serial Number {sno}    ", end="\r")
            itd = frappe.get_doc("Item", op.production_item)
            if not any(d["production_item"] == op.production_item and d["operation"] == op.operation \
                       for d in done_ops) and itd.made_to_order != 1:
                done_op_dict["production_item"] = op.production_item
                done_op_dict["operation"] = op.operation
                done_ops.append(done_op_dict.copy())
                # Pending PS Operation Qty should be Equal to Planned + Actual in WIP Warehouse + In Subcontract WH
                all_ops = get_pend_psop(it_name=op.production_item, operation=op.operation, tf_ent=1)
                stopped_ops, changed_ops, unchanged_ops, tot_changes, create_nos = \
                    stop_or_change_ops(op_dict=all_ops, stop_nos=stopped_ops, change_nos=changed_ops,
                                       un_nos=unchanged_ops, tot_changes=tot_changes, itd=itd, create_nos=create_nos)
                if tot_changes > 0 and tot_changes % 100 == 0:
                    print(f"Committing Changes after {tot_changes} Changes and Time Taken = "
                          f"{int(time.time() - st_time)} seconds")
                    frappe.db.commit()
    print(f"Total Ops Stopped = {stopped_ops} and Operations Changed = {changed_ops} and Unchanged Operations = "
          f"{unchanged_ops} and Created JCRs = {create_nos} and Total Time Taken = {int(time.time() - st_time)} seconds")


def stop_or_change_ops(op_dict, stop_nos, change_nos, un_nos, tot_changes, itd, create_nos):
    for i in range(0, len(op_dict)):
        psd = frappe.get_doc("Process Sheet", op_dict[i].ps_name)
        if i < len(op_dict) - 1:
            tot_changes += 1
            stop_nos += 1
            print(f"Stopped Operation {op_dict[i].operation} for {itd.name} for "
                  f"Process Sheet {op_dict[i].ps_name}")
            stop_ps_operation(psd=psd, op_id=op_dict[i].name)
        else:
            # Create Job Card if Not There if qty diff then change in existing JCR or create new
            # If qty is same then close old operations and create JCR from new ones.
            exist_jcr = check_existing_job_card(item_name=itd.name, operation=op_dict[i].operation, ps_doc=psd)
            op_qty = get_actual_qty_before_process_in_ps(psd=psd, itd=itd, operation=op_dict[i].operation)
            new_op_planned_qty = op_qty + op_dict[i].completed_qty
            if op_qty > 0:
                if op_qty != op_dict[i].op_pen_qty:
                    if op_qty > op_dict[i].op_pen_qty:
                        type_of_change = "Increased"
                    else:
                        type_of_change = "Decreased"
                    change_nos += 1
                    tot_changes += 1
                    frappe.db.set_value("BOM Operation", op_dict[i].name, "planned_qty", new_op_planned_qty)
                    if exist_jcr:
                        if len(exist_jcr) == 1:
                            jcd = frappe.get_doc("Process Job Card RIGPL", exist_jcr[0].name)
                            if jcd.operation_id == op_dict[i].name:
                                jcd.for_quantity = op_qty
                                jcd.time_logs = []
                                jcd.save()
                                print(f"{type_of_change} Qty for JCR# {jcd.name} for Operation {op_dict[i].operation} "
                                      f"for Item:{op_dict[i].production_item} for Process Sheet {op_dict[i].ps_name} "
                                      f"from Old Qty = {op_dict[i].op_pen_qty} to New Qty = {op_qty}")
                            else:
                                tot_changes += 1
                                print(f"Deleted JCR# {jcd.name} for Operation {op_dict[i].operation} for "
                                      f"Item:{op_dict[i].production_item} for Process Sheet {op_dict[i].ps_name}")
                                frappe.delete_doc('Process Job Card RIGPL', jcd.name, for_reload=True)
                        else:
                            print(f"For Item: {itd.name} and Operation: {op_dict[i].operation} there are "
                                  f"{len(exist_jcr)} Job Cards. Kindly remove this to proceed.")
                            exit()
                    else:
                        tot_changes += 1
                        create_nos += 1
                        print(f"Created JCR for Operation {op_dict[i].operation} for {op_dict[i].production_item} "
                              f"for Process Sheet {op_dict[i].ps_name} for Quantity = {op_qty}")
                        create_job_card(pro_sheet=psd, row=op_dict[i], quantity=op_qty, auto_create=1)
                else:
                    # Create Job Card if Not There
                    if not exist_jcr:
                        tot_changes += 1
                        un_nos += 1
                        create_nos += 1
                        print(f"Created JCR for Operation {op_dict[i].operation} for {op_dict[i].production_item} "
                              f"for Process Sheet {op_dict[i].ps_name} for Quantity = {op_qty}")
                        create_job_card(pro_sheet=psd, row=op_dict[i], quantity=op_qty, auto_create=1)
            else:
                # Since no Qty in For Operation hence stop all the Operations
                tot_changes += 1
                stop_nos += 1
                print(f"Stopped Operation {op_dict[i].operation} for {op_dict[i].production_item} for "
                      f"Process Sheet {op_dict[i].ps_name} as No Qty in Manufacturing before this Operation")
                stop_ps_operation(psd=psd, op_id=op_dict[i].name)
    return stop_nos, change_nos, un_nos, tot_changes, create_nos


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
    FROM `tabItem` it 
        LEFT JOIN `tabItem Reorder` it_rol ON it_rol.parent = it.name AND it_rol.parenttype = 'Item' 
    WHERE it.disabled = 0 AND it.include_item_in_manufacturing = 1 AND it.has_variants = 0 AND it.variant_of IS NOT NULL 
    ORDER BY vr_rol DESC, vrate DESC, wh_rol DESC, name ASC""", as_dict=1)
    print(f"Total Items Being Considered for Auto Process Sheet = {len(it_dict)}")
    created = 0
    err_it = []
    for it in it_dict:
        vr_rol = flt(it.vrate) * flt(it.wh_rol)
        # print(f"Considering {it.name} ROL= {it.wh_rol} with Value = {it.vrate} AND VR*ROL = {vr_rol}")
        it_doc = frappe.get_doc("Item", it.name)
        qty, max_qty = get_qty_to_manufacture(it_doc)
        value_for_manf = qty * it.vrate
        if value_for_manf >= value:
            # Check if existing or create new
            created = check_exist_ps(it_name=it.name, for_qty=qty, vr_rol=vr_rol, err_it=err_it, created=created)
        else:
            if qty > 0:
                qty_dict = get_quantities_for_item(it_doc)
                if qty_dict.on_so > 0:
                    # Create PS only if SO qty is MORE than qty in Stock or WIP or PO
                    if qty_dict.on_so > (qty_dict.on_po + qty_dict.planned_qty + qty_dict.finished_qty +
                                         qty_dict.wip_qty + qty_dict.dead_qty + qty_dict.planned_qty) - \
                            qty_dict.reserved_for_prd:
                        created = check_exist_ps(it_name=it.name, for_qty=qty, vr_rol=vr_rol, err_it=err_it,
                                                 created=created)
    print(f"List of Items where New Process Sheet cannot be Made \n {err_it}")
    it_time = int(time.time() - st_time)
    print(f"Total Process Sheets Created = {created}")
    print(f"Total Time for Creation of Process Sheets = {it_time} seconds")


def check_exist_ps(it_name, for_qty, vr_rol, err_it, created):
    # Check if existing or create new
    existing_ps = frappe.db.sql("""SELECT name FROM `tabProcess Sheet` WHERE docstatus=0 
    AND production_item= '%s'""" % it_name, as_dict=1)
    if existing_ps:
        ex_ps = frappe.get_doc("Process Sheet", existing_ps[0].name)
        if ex_ps.quantity != for_qty:
            old_qty = ex_ps.quantity
            ex_ps.quantity = for_qty
            print(f"Updated {ex_ps.name} Changed Quantity from {old_qty} to {for_qty} for {it_name} "
                  f"VR*ROL = {vr_rol}")
            try:
                ex_ps.save()
            except:
                frappe.db.set_value("Process Sheet", ex_ps.name, "quantity", for_qty)
                print(f"Updated {ex_ps.name} Changed Quantity from {old_qty} to {for_qty} for {it_name} "
                      f"VR*ROL = {vr_rol}")
    else:
        created = create_new_ps_from_item(it_name=it_name, for_qty=for_qty, err_it=err_it, vr_rol=vr_rol,
                                          created=created)
    return created


def update_process_sheet_status():
    st_time = time.time()
    ps_count = 0
    ps_dict = get_pend_psop()
    ps_dict = sorted(ps_dict, key=itemgetter("ps_name", "idx"))
    print(f"Total No of Process Sheet Processes Being Considered = {len(ps_dict)}")
    for ps in ps_dict:
        print(f"{ps} \n")
    exit()
    for i in range(len(ps_dict)):
        if i > 0:
            if ps_dict[i].ps_name != ps_dict[i-1].ps_name:
                ps_count = process_sheet_status(ps_dict[i].ps_name, st_time, ps_count)
        else:
            ps_count = process_sheet_status(ps_dict[i].ps_name, st_time, ps_count)
    end_time = time.time()
    tot_ps_time = round(end_time - st_time)
    print(f"Total Process Sheet Status Updated = {ps_count}")
    print(f"Total Time Taken for Process Sheets is {tot_ps_time} seconds")


def create_new_ps_from_item(it_name, for_qty, vr_rol, err_it, created):
    try:
        ps = frappe.new_doc("Process Sheet")
        ps.production_item = it_name
        ps.date = today()
        ps.quantity = for_qty
        ps.status = "Draft"
        ps.insert()
        frappe.db.commit()
        print(f"Created {ps.name} for {it_name} for Qty= {for_qty} VR*ROL = {vr_rol}")
        created += 1
    except Exception as e:
        err_it.append(it_name)
        print(f"Error Encountered while Creating Process Sheet for {it_name} Qty = {for_qty} "
              f"VR*ROL = {vr_rol} and Error = {e}")
    return created


def process_sheet_status(ps_name, st_time, ps_count):
    # print(f"Processing {ps_name}. Time Elapsed = {int(time.time() - st_time)} seconds")
    ps_doc = frappe.get_doc("Process Sheet", ps_name)
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
