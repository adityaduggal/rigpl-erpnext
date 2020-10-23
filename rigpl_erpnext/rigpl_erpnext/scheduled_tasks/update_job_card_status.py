# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from erpnext.stock.utils import get_bin


def execute():
    open = "Open"
    wip = "Work In Progress"
    start_time = time.time()
    jc_dict = frappe.db.sql("""SELECT name, status FROM `tabProcess Job Card RIGPL` 
    WHERE docstatus = 0 ORDER BY name""", as_dict=1)
    updated_jc_nos = 0
    for jc in jc_dict:
        changed_status_for_jc = 0
        jc_doc = frappe.get_doc("Process Job Card RIGPL", jc.name)
        op_doc = frappe.get_doc("BOM Operation", jc_doc.operation_id)
        if op_doc.idx == 1:
            if jc_doc.status != wip:
                updated_jc_nos += 1
                changed_status_for_jc = 1
                jc_doc.status = wip
                print("Updated Status of JC# {} to {}}".format(jc.name, wip))
        else:
            pro_doc = frappe.get_doc('Process Sheet', jc_doc.process_sheet)
            if pro_doc.sales_order_item:
                for prev_op in pro_doc.operations:
                    if prev_op.idx == op_doc.idx - 1:
                        prev_op_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE 
                        operation_id = '%s' AND docstatus != 2""" % prev_op.name, as_dict=1)
                        if prev_op_jc:
                            prev_op_jc_doc = frappe.get_doc("Process Job Card RIGPL", prev_op_jc[0].name)
                            if prev_op_jc_doc.status == "Completed":
                                if jc_doc.status != wip:
                                    updated_jc_nos += 1
                                    changed_status_for_jc = 1
                                    jc_doc.status = wip
                                    print("Updated Status of JC# {} to {}".format(jc.name, wip))
                            else:
                                if jc_doc.status != open:
                                    updated_jc_nos += 1
                                    changed_status_for_jc = 1
                                    jc_doc.status = open
                                    print("Updated Status of JC# {} to {}".format(jc.name, open))
                        else:
                            frappe.throw("For Item: {} in JC# {} there is no Reference for Previous "
                                         "Process".foramt(jc_doc.production_item, jc_doc.name))
            else:
                # Now the JC is for Items with Attributes or Stock Items. They can be WIP if there is stock in
                # Source Warehouse
                qty_available = get_bin(jc_doc.production_item, jc_doc.s_warehouse).get("actual_qty")
                if qty_available > 0:
                    if jc_doc.status != wip:
                        updated_jc_nos += 1
                        changed_status_for_jc = 1
                        jc_doc.status = wip
                        print("Updated Status of JC# {} to {}".format(jc.name, wip))
                else:
                    if jc_doc.status != "Open":
                        updated_jc_nos += 1
                        changed_status_for_jc = 1
                        jc_doc.status = 'Open'
                        print("Updated Status of JC# {} to {}".format(jc.name, open))
        if changed_status_for_jc == 1:
            jc_doc.save()

    end_time = time.time()
    print("Total Number of Job Cards in Draft: " + str(len(jc_dict)))
    print("Total Number of Job Cards with Wrong Status: " + str(updated_jc_nos))
    print(f"Total Execution Time: {end_time - start_time} seconds")