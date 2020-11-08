# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from ...utils.job_card_utils import update_job_card_qty_available, update_job_card_status, update_job_card_priority


def execute():
    open = "Open"
    wip = "Work In Progress"
    start_time = time.time()
    jc_dict = frappe.db.sql("""SELECT name, status FROM `tabProcess Job Card RIGPL` 
    WHERE docstatus = 0 ORDER BY name""", as_dict=1)
    updated_jc_nos = 0
    for jc in jc_dict:
        jc_doc = frappe.get_doc("Process Job Card RIGPL", jc.name)
        old_qty_available = jc_doc.qty_available
        old_priority = jc_doc.priority
        old_status = jc_doc.status
        update_job_card_qty_available(jc_doc)
        update_job_card_status(jc_doc)
        update_job_card_priority(jc_doc)
        new_qty_available = jc_doc.qty_available
        new_priority = jc_doc.priority
        new_status = jc_doc.status
        if old_qty_available != new_qty_available or old_status != new_status or old_priority != new_priority:
            updated_jc_nos += 1
            try:
                jc_doc.save()
                print("Updated Job Card # {}".format(jc_doc.name))
            except:
                print(f"Some Error for JC# {jc_doc.name}")
    end_time = time.time()
    total_time = int(end_time - start_time)
    print("Total Number of Job Cards in Draft: " + str(len(jc_dict)))
    print("Total Number of Job Cards Updated: " + str(updated_jc_nos))
    print(f"Total Execution Time: {total_time} seconds")