# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from frappe.utils.background_jobs import enqueue
from ...utils.process_sheet_utils import update_process_sheet_operations, get_pend_psop
from ...utils.job_card_utils import check_existing_job_card, create_job_card, return_job_card_qty


def enqueue_jc():
    """
    Enqueues the Creation of Job Cards Process with longer time out
    """
    enqueue(execute, queue="long", timeout=600)


def execute():
    """
    Delete Obsolete JCR
    """
    st_time = time.time()
    deleted_jcr = 0
    changed_jcr = 0
    sc_jcr = 0
    draft_jc = frappe.db.sql("""SELECT name, priority, sales_order_item, operation_id,
        process_sheet, for_quantity,total_qty  FROM `tabProcess Job Card RIGPL`
        WHERE docstatus = 0 AND (priority = 999 OR total_qty = 0 OR for_quantity = 0)
        ORDER BY creation, name""", as_dict=1)
    print(f"Total No of Job Cards with 999 Priority or ZERO Total Qty OR ZERO FOR QTY = "
        f"{len(draft_jc)}")
    for jcr in draft_jc:
        jcd = frappe.get_doc("Process Job Card RIGPL", jcr.name)
        # Only check the Order Items and delete them if Order Already Dispatched and Short Close the Process
        if jcr.sales_order_item:
            pending_so = frappe.db.sql(f"""SELECT (soi.qty - soi.delivered_qty) AS pend_qty
                FROM `tabSales Order` so, `tabSales Order Item` soi
                WHERE soi.parent = so.name AND so.docstatus = 1 AND so.status != 'Closed'
                AND soi.qty > soi.delivered_qty
                AND soi.name = '{jcr.sales_order_item}'""", as_dict=1)
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
                        print(f"Pending SO exists for {jcr.name} and Priority = {jcr.priority}, "
                            f"Tot Qty = {jcr.total_qy} and  For Qty = {jcr.for_quantity}."
                            "You might wanna check why?")
        else:
            save_failed = 0
            if jcr.total_qty == 0 or jcr.for_quantity == 0:
                # First Try and recalculate the quantities by saving if successful in saving and
                # still zero then delete
                jcd = frappe.get_doc("Process Job Card RIGPL", jcr.name)
                try:
                    jcd.save()
                    changed_jcr += 1
                except:
                    save_failed = 1
                    print(f"Unable to Save {jcr.name} for Process Sheet {jcd.process_sheet}")
                if save_failed != 1 and (jcd.for_quantity == 0 or jcd.total_qty == 0):
                    deleted_jcr += 1
                    print(f"Deleting {jcd.name} as ZERO Total Qty or For Quantity is ZERO")
                    frappe.delete_doc("Process Job Card RIGPL", jcr.name, for_reload=True)
    frappe.db.commit()
    jc_del_time = int(time.time() - st_time)
    print(f"Total No of Job Cards Deleted = {deleted_jcr}")
    print(f"Total No of Job Cards Short Closed = {sc_jcr}")
    print(f"Total No of Job Cards Updated = {changed_jcr}")
    print(f"Total Time Taken for Deleting Job Cards = {jc_del_time} seconds")



def create_production_job_cards():
    """
    Would only create the Job Cards for Entries where transfer entries = 0 that means only
    for PS where RM is consumed
    """
    st_time = time.time()
    pending_psheets = get_pend_psop(tf_ent=0)
    print(f"Total Pending Process Sheets Operations to be Checked {len(pending_psheets)}")
    jcr_created = 0
    if pending_psheets:
        for psh in pending_psheets:
            psd = frappe.get_doc("Process Sheet", psh.ps_name)
            opd = frappe.get_doc("BOM Operation", psh.name)
            qty = psh.planned_qty - psh.completed_qty
            exist_jc = check_existing_job_card(item_name=psh.production_item,
                operation=psh.operation, so_detail=psh.sales_order_item, ps_doc=psd)
            if not exist_jc:
                jcr_created += 1
                create_job_card(pro_sheet=psd, row=opd, quantity=qty, auto_create=True)
                update_process_sheet_operations(ps_name=psh.ps_name, op_name=psh.name)
            if jcr_created > 0 and jcr_created % 50 == 0:
                print(f"Committing Changes after making {jcr_created} Changes. Total Time Taken = "
                      f"{int(time.time() - st_time)}")
                frappe.db.commit()
    tot_time = int(time.time() - st_time)
    print(f"Total JC Created = {jcr_created} and Time Taken for JCR Creation {tot_time} seconds")
