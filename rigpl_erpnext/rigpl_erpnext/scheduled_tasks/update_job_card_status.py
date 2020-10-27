# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from ...utils.job_card_utils import update_job_card_qty_available, update_job_card_status


def execute():
    open = "Open"
    wip = "Work In Progress"
    start_time = time.time()
    jc_dict = frappe.db.sql("""SELECT name, status FROM `tabProcess Job Card RIGPL` 
    ORDER BY name""", as_dict=1)
    updated_jc_nos = 0
    for jc in jc_dict:
        jc_doc = frappe.get_doc("Process Job Card RIGPL", jc.name)
        ps_doc = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
        old_qty_available = jc_doc.qty_available
        old_status = jc_doc.status
        update_job_card_qty_available(jc_doc)
        update_job_card_status(jc_doc)
        new_qty_available = jc_doc.qty_available
        new_status = jc_doc.status
        if old_qty_available != new_qty_available or old_status != new_status:
            updated_jc_nos += 1
            jc_doc.save()
            print("Updated Job Card # {}".format(jc_doc.name))
            if updated_jc_nos % 10 == 0 and updated_jc_nos > 0:
                frappe.db.commit()
                print("Committing Changes after {} Nos JC Updation".format(updated_jc_nos))
    end_time = time.time()
    print("Total Number of Job Cards in Draft: " + str(len(jc_dict)))
    print("Total Number of Job Cards Updated: " + str(updated_jc_nos))
    print(f"Total Execution Time: {end_time - start_time} seconds")