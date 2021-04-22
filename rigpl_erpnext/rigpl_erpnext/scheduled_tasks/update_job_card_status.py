# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import time
import datetime
import frappe
from ...utils.job_card_utils import update_job_card_qty_available, update_job_card_status, update_job_card_priority, \
    update_job_card_source_warehouse, return_job_card_qty, get_jc_rm_status, update_jc_rm_status


def update_rm_status_unmodified():
    st_time = time.time()
    jc_dict = frappe.db.sql("""SELECT name, creation, modified FROM `tabProcess Job Card RIGPL` 
    WHERE docstatus = 0 AND allow_consumption_of_rm = 1 ORDER BY creation DESC""", as_dict=1)
    print(f"Total Number of Draft JC for RM Consumption = {len(jc_dict)}")
    no_mod = 0
    stale_mod = 0
    for jc in jc_dict:
        if jc.creation == jc.modified:
            no_mod += 1
            update_jc_rm_status(jc.name)
        elif (datetime.datetime.now() - jc.modified).seconds / 3600 > 6:
            stale_mod += 1
            update_jc_rm_status(jc.name)

    no_rm_jc_nos = 0
    no_rm_jc = frappe.db.sql("""SELECT name, creation, modified FROM `tabProcess Job Card RIGPL` 
    WHERE docstatus = 0 AND allow_consumption_of_rm = 0 AND transfer_entry = 0 ORDER BY creation DESC""", as_dict=1)
    print(f"Total No of JC without RM and without Transfer = {len(no_rm_jc)}")

    for jc in no_rm_jc:
        jcd = frappe.get_doc("Process Job Card RIGPL", jc.name)
        jcd.time_logs = []
        try:
            jcd.save()
            no_rm_jc_nos += 1

        except Exception as e:
            print(f"Some Error in JCR# {jcd.name} and Error is {e}")

    print(f"Total Not Modified JCR changed = {no_mod}")
    print(f"Total JCR Modified after 6 hours = {stale_mod}")
    print(f"Total No of JC without RM and without Transfer Updated = {no_rm_jc_nos}")
    print(f"Total Time Taken = {int(time.time() - st_time)} seconds")


def update_jc_rm_status(jc_name):
    jcd = frappe.get_doc("Process Job Card RIGPL", jc_name)
    new_rm_status, new_rm_shortage = get_jc_rm_status(jcd)
    if new_rm_shortage != jcd.rm_shortage or new_rm_status != jcd.rm_status:
        jcd.rm_status = new_rm_status
        jcd.rm_shortage = new_rm_shortage
    jcd.time_logs = []
    try:
        jcd.save()
    except Exception as e:
        print(f"Some Error in JCR# {jcd.name} and Error is {e}")


def execute():
    start_time = time.time()
    jc_dict = frappe.db.sql("""SELECT name, status, creation, modified FROM `tabProcess Job Card RIGPL` 
    WHERE docstatus = 0 ORDER BY modified, name""", as_dict=1)
    updated_jc_nos = 0
    for jc in jc_dict:
        if (datetime.datetime.now() - jc.modified).seconds / 3600 > 6:
            jc_doc = frappe.get_doc("Process Job Card RIGPL", jc.name)
            old_tot_qty = jc_doc.total_qty
            new_tot_qty = jc_doc.total_qty
            old_qty_available = jc_doc.qty_available
            old_priority = jc_doc.priority
            old_status = jc_doc.status
            update_job_card_qty_available(jc_doc)
            update_job_card_status(jc_doc)
            s_wh_changed = update_job_card_source_warehouse(jc_doc)
            update_job_card_priority(jc_doc)
            new_qty_available = jc_doc.qty_available
            new_priority = jc_doc.priority
            new_status = jc_doc.status
            if old_qty_available != new_qty_available or old_status != new_status or old_priority != new_priority or \
                    s_wh_changed == 1 or old_tot_qty != new_tot_qty:
                updated_jc_nos += 1
                try:
                    jc_doc.save()
                    print(f"{updated_jc_nos}. Updated Job Card # {jc_doc.name}")
                except Exception as e:
                    print(f"Some Error for JC# {jc_doc.name} and the Exception Occurred is {e}")
                if updated_jc_nos % 100 == 0 and updated_jc_nos > 0:
                    frappe.db.commit()
                    print(f"Committing Changes to DB after {updated_jc_nos} Changes Total "
                          f"Time Elapsed = {int(time.time() - start_time)} seconds")
    end_time = time.time()
    total_time = int(end_time - start_time)
    print("Total Number of Job Cards in Draft: " + str(len(jc_dict)))
    print("Total Number of Job Cards Updated: " + str(updated_jc_nos))
    print(f"Total Execution Time: {total_time} seconds")