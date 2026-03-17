# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import time
import datetime
import frappe
from frappe.utils.background_jobs import enqueue
from rigpl_erpnext.manufacturing_rigpl.utils.job_card_utils import update_job_card_qty_available, update_job_card_status, update_job_card_priority, \
    update_job_card_source_warehouse, return_job_card_qty, get_jc_rm_status, update_jc_rm_status


def update_rm_status_unmodified():
    st_time = time.time()
    jc_dict = frappe.db.sql("""SELECT name, creation, modified FROM `tabProcess Job Card RIGPL`
    WHERE docstatus = 0 AND allow_consumption_of_rm = 1 ORDER BY creation DESC""", as_dict=1)
    
    no_rm_jc = frappe.db.sql("""SELECT name, creation, modified FROM `tabProcess Job Card RIGPL`
    WHERE docstatus = 0 AND allow_consumption_of_rm = 0 AND transfer_entry = 0 ORDER BY creation DESC""", as_dict=1)
    
    print(f"Total Number of Draft JC for RM Consumption = {len(jc_dict)}")
    print(f"Total No of JC without RM and without Transfer = {len(no_rm_jc)}")
    
    now_dt = datetime.datetime.now()
    no_mod, stale_mod, updated_nos = 0, 0, 0

    # Process JC with RM
    for jc in jc_dict:
        should_update = False
        if jc.creation == jc.modified:
            no_mod += 1
            should_update = True
        elif (now_dt - jc.modified).total_seconds() / 3600 > 6:
            stale_mod += 1
            should_update = True
        
        if should_update:
            update_jc_rm_status(jc.name)
            updated_nos += 1
            if updated_nos % 50 == 0:
                frappe.db.commit()

    # Process JC without RM
    for jc in no_rm_jc:
        jcd = frappe.get_doc("Process Job Card RIGPL", jc.name)
        if len(jcd.time_logs) > 0:
            jcd.time_logs = []
            try:
                jcd.save()
                updated_nos += 1
            except Exception as e:
                print(f"Error in JCR# {jc.name}: {e}")
        
        if updated_nos % 50 == 0:
            frappe.db.commit()

    print(f"Total Not Modified JCR changed = {no_mod}")
    print(f"Total JCR Modified after 6 hours = {stale_mod}")
    print(f"Total No of Updates = {updated_nos}")
    print(f"Total Time Taken = {int(time.time() - st_time)} seconds")
    frappe.db.commit()


def update_jc_rm_status(jc_name):
    jcd = frappe.get_doc("Process Job Card RIGPL", jc_name)
    new_rm_status, new_rm_shortage = get_jc_rm_status(jcd)
    changed = False
    if new_rm_shortage != jcd.rm_shortage or new_rm_status != jcd.rm_status:
        jcd.rm_status = new_rm_status
        jcd.rm_shortage = new_rm_shortage
        changed = True
    
    if len(jcd.time_logs) > 0:
        jcd.time_logs = []
        changed = True
        
    if changed:
        try:
            jcd.save()
        except Exception as e:
            print(f"Error saving JCR# {jc_name}: {e}")


def enqueue_jc_status_update():
    enqueue(execute, queue="long", timeout=1500)


def execute():
    start_time = time.time()
    jc_dict = frappe.db.sql("""SELECT name, status, creation, modified, production_item, process_sheet 
        FROM `tabProcess Job Card RIGPL`
        WHERE docstatus = 0 ORDER BY modified, name""", as_dict=1)
    
    if not jc_dict:
        return

    # Bulk fetch related data to avoid massive N+1 in job_card_utils functions
    ps_names = list(set([jc.process_sheet for jc in jc_dict]))
    process_sheets = frappe.get_all("Process Sheet", filters={"name": ["in", ps_names]}, 
        fields=["name", "bom_template", "sales_order", "sales_order_item", "sno"])
    ps_map = {ps.name: ps for ps in process_sheets}

    bt_names = list(set([ps.bom_template for ps in process_sheets]))
    bom_templates = frappe.get_all("BOM Template RIGPL", filters={"name": ["in", bt_names]})
    # We need the full doc for BOM Template because get_job_card_process_sno iterates over operations
    bt_map = {bt.name: frappe.get_doc("BOM Template RIGPL", bt.name) for bt in bom_templates}

    item_names = list(set([jc.production_item for jc in jc_dict]))
    items = frappe.get_all("Item", filters={"name": ["in", item_names]})
    item_map = {it.name: frappe.get_doc("Item", it.name) for it in items}

    updated_jc_nos = 0
    now_dt = datetime.datetime.now()

    for jc in jc_dict:
        if (now_dt - jc.modified).total_seconds() / 3600 > 6:
            jc_doc = frappe.get_doc("Process Job Card RIGPL", jc.name)
            
            ps_doc = ps_map.get(jc_doc.process_sheet)
            bt_doc = bt_map.get(ps_doc.bom_template) if ps_doc else None
            it_doc = item_map.get(jc_doc.production_item)

            old_qty_available = jc_doc.qty_available
            old_priority = jc_doc.priority
            old_status = jc_doc.status
            old_tot_qty = jc_doc.total_qty

            # Pruning the call stack N+1 by fetching them into cache
            if ps_doc: frappe.get_cached_doc("Process Sheet", ps_doc.name)
            if bt_doc: frappe.get_cached_doc("BOM Template RIGPL", bt_doc.name)
            if it_doc: frappe.get_cached_doc("Item", it_doc.name)

            update_job_card_qty_available(jc_doc)
            update_job_card_status(jc_doc)
            s_wh_changed = update_job_card_source_warehouse(jc_doc)
            update_job_card_priority(jc_doc)

            if old_qty_available != jc_doc.qty_available or old_status != jc_doc.status or \
                    old_priority != jc_doc.priority or s_wh_changed == 1 or old_tot_qty != jc_doc.total_qty:
                updated_jc_nos += 1
                try:
                    jc_doc.save()
                    print(f"{updated_jc_nos}. Updated Job Card # {jc_doc.name}")
                except Exception as e:
                    print(f"Error for JC# {jc_doc.name}: {e}")
                
                if updated_jc_nos % 100 == 0:
                    frappe.db.commit()
    
    frappe.db.commit()
    print(f"Total Job Cards in Draft: {len(jc_dict)}")
    print(f"Total Updated: {updated_jc_nos}")
    print(f"Total Time: {int(time.time() - start_time)} seconds")
    end_time = time.time()
    total_time = int(end_time - start_time)
    print("Total Number of Job Cards in Draft: " + str(len(jc_dict)))
    print("Total Number of Job Cards Updated: " + str(updated_jc_nos))
    print(f"Total Execution Time: {total_time} seconds")
