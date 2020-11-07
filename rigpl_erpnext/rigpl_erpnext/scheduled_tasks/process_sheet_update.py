# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from ...utils.process_sheet_utils import make_jc_for_process_sheet, update_process_sheet_quantities


def execute():
    st_time = time.time()
    ps_dict = frappe.db.sql("""SELECT name, status FROM `tabProcess Sheet` 
    WHERE docstatus = 1 AND status != 'Completed' AND status != 'Stopped' AND status != 'Short Closed' 
    ORDER BY name""", as_dict=1)
    ps_count = 0
    for ps in ps_dict:
        ps_doc = frappe.get_doc("Process Sheet", ps.name)
        make_jc_for_process_sheet(ps_doc)
        update_process_sheet_quantities(ps_doc)
        if ps_doc.short_closed_qty > 0:
            ps_doc.status = "Short Closed"
            print("Short Closed {}".format(ps_doc.name))
        elif ps_doc.quantity <= ps_doc.produced_qty:
            ps_count += 1
            ps_doc.status = "Completed"
            print("Completed {}".format(ps_doc.name))
        else:
            if ps_doc.status == "Submitted":
                for op in ps_doc.operations:
                    if op.completed_qty > 0:
                        ps_count += 1
                        ps_doc.status = "In Progress"
                        print("In Progress Status set for {}".format(ps_doc.name))
        ps_doc.save()
    end_time = time.time()
    tot_time = round(end_time - st_time)
    print(f"Total Process Sheet Status Updated = {ps_count}")
    print(f"Total Time Taken {tot_time} seconds")
