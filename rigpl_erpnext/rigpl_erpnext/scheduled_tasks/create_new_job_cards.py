# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from frappe.utils.background_jobs import enqueue
from ...utils.process_sheet_utils import update_process_sheet_operations
from ...utils.job_card_utils import check_existing_job_card, create_job_card, return_job_card_qty


def enqueue_jc():
    enqueue(execute, queue="long", timeout=600)


def execute():
    st_time = time.time()
    deleted_jcr = 0
    changed_jcr = 0
    sc_jcr = 0
    draft_jc = frappe.db.sql("""SELECT name, priority, sales_order_item, operation_id, process_sheet, for_quantity,
    total_qty 
    FROM `tabProcess Job Card RIGPL` WHERE docstatus = 0 AND (priority = 999 OR total_qty = 0 OR for_quantity = 0)
    ORDER BY creation, name""", as_dict=1)
    print(f"Total No of Job Cards with 999 Priority or ZERO Total Qty OR ZERO FOR QTY = {len(draft_jc)}")
    for jc in draft_jc:
        # print(f"{sno}. Checking and trying to Close {jc.name} for PS# {jc.process_sheet}")
        jcd = frappe.get_doc("Process Job Card RIGPL", jc.name)
        # Only check the Order Items and delete them if Order Already Dispatched and Short Close the Process
        if jc.sales_order_item:
            pending_so = frappe.db.sql("""SELECT (soi.qty - soi.delivered_qty) AS pend_qty FROM `tabSales Order` so,
            `tabSales Order Item` soi WHERE soi.parent = so.name AND so.docstatus = 1 AND so.status != 'Closed'
            AND soi.qty > soi.delivered_qty AND soi.name = '%s'""" % jc.sales_order_item, as_dict=1)
            if not pending_so:
                jcd.no_stock_entry = 1
                jcd.short_close_operation = 1
                try:
                    jcd.submit()
                    sc_jcr += 1
                except:
                    print(f"Some Error While Submitting {jcd.name}")
            else:
                tot_qty, for_qty = return_job_card_qty(jcd)
                if tot_qty != jcd.total_qty or for_qty != jcd.for_quantity:
                    jcd.total_qty = tot_qty
                    jcd.for_quantity = for_qty
                    try:
                        jcd.save()
                        changed_jcr += 1
                    except:
                        print(f"Pending SO exists for {jc.name} and Priority = {jc.priority}, Tot Qty = {jc.total_qy} "
                              f"and  For Qty = {jc.for_quantity}.You might wanna check why?")
        else:
            save_failed = 0
            if jc.total_qty == 0 or jc.for_quantity == 0:
                # First Try and recalculate the quantities by saving if successful in saving and still zero then delete
                jcd = frappe.get_doc("Process Job Card RIGPL", jc.name)
                try:
                    jcd.save()
                    changed_jcr += 1
                except:
                    save_failed = 1
                    print(f"Unable to Save {jc.name} for Process Sheet {jcd.process_sheet}")
                if save_failed != 1 and (jcd.for_quantity == 0 or jcd.total_qty == 0):
                    deleted_jcr += 1
                    print(f"Deleting {jcd.name} as ZERO Total Qty or For Quantity is ZERO")
                    frappe.delete_doc("Process Job Card RIGPL", jc.name, for_reload=True)
    frappe.db.commit()
    jc_del_time = int(time.time() - st_time)
    print(f"Total No of Job Cards Deleted = {deleted_jcr}")
    print(f"Total No of Job Cards Short Closed = {sc_jcr}")
    print(f"Total No of Job Cards Updated = {changed_jcr}")
    print(f"Total Time Taken for Deleting Job Cards = {jc_del_time} seconds")
    time.sleep(2)

    pending_psheets = frappe.db.sql("""SELECT ps.name, pso.name AS op_id, pso.operation, pso.planned_qty, 
    pso.completed_qty, pso.status AS op_status, ps.status, ps.production_item, pso.operation, ps.sales_order_item
    FROM `tabProcess Sheet` ps, `tabBOM Operation` pso WHERE ps.docstatus = 1 AND pso.parent = ps.name 
    AND pso.parenttype = 'Process Sheet' AND pso.status != 'Completed' AND pso.status != 'Short Closed' 
    AND pso.status != 'Stopped' AND pso.status != 'Obsolete' AND ps.status != 'Short Closed' AND ps.status != 'Stopped'
    AND pso.planned_qty > pso.completed_qty
    ORDER BY ps.creation ASC, pso.idx ASC""", as_dict=1)
    print(f"Total Pending Process Sheets Operations to be Checked {len(pending_psheets)}")
    time.sleep(1)
    jcr_created = 0
    tot_ps_op = 0
    if pending_psheets:
        for ps in pending_psheets:
            tot_ps_op += 1
            psd = frappe.get_doc("Process Sheet", ps.name)
            opd = frappe.get_doc("BOM Operation", ps.op_id)
            qty = ps.planned_qty - ps.completed_qty
            exist_jc = check_existing_job_card(item_name=ps.production_item, operation=ps.operation,
                                               so_detail=ps.sales_order_item, ps_doc=psd)
            if not exist_jc:
                jcr_created += 1
                create_job_card(pro_sheet=psd, row=opd, quantity=qty, auto_create=True)
                update_process_sheet_operations(ps_name=ps.name, op_name=ps.op_id)
            if jcr_created > 0 and jcr_created % 50 == 0:
                print(f"Committing Changes after making {jcr_created} Changes. Total Time Taken = "
                      f"{int(time.time() - st_time) - jc_del_time}")
                frappe.db.commit()
    print(f"{tot_ps_op}")
    tot_time = int(time.time() - st_time) - jc_del_time
    print(f"Total Job Cards Created = {jcr_created}")
    print(f"Total Time Taken {tot_time} seconds")
