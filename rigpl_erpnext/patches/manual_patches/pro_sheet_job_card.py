# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import time
from ...utils.process_sheet_utils import update_process_sheet_operations, update_process_sheet_op_planned_qty

# This patch would check the completed quantity in Process Sheet Operations and Correct them if needed
# This would also update the total qty in Job Card field


def execute():
    st_time = time.time()
    edits = 0
    sno = 1
    ps_processes = frappe.db.sql("""SELECT ps.name, pso.name as op_name, pso.operation, pso.planned_qty, 
    pso.completed_qty, pso.idx, pso.status as op_status, ps.status
    FROM `tabProcess Sheet` ps, `tabBOM Operation` pso
    WHERE pso.parent = ps.name AND pso.parenttype = 'Process Sheet' AND ps.docstatus = 1 AND pso.status != "Completed" 
    AND pso.status != "Short Closed"
    ORDER BY ps.name, pso.idx""", as_dict=1)
    print(f"Total Operations Pending = {len(ps_processes)}")
    time.sleep(2)
    for ps in ps_processes:
        # print(f"Checking {ps.name} for Row# {ps.idx}")
        changes = update_process_sheet_operations(ps.name, ps.op_name)
        changes = update_process_sheet_op_planned_qty(ps.name, ps.op_name)
        if changes == 1:
            print(f"{sno}. Changes Made to {ps.name} for Row# {ps.idx}")
            sno += 1
            edits += 1
        if edits % 500 == 0 and edits > 0 and changes == 1:
            print(f"Committing after {edits} Changes. Elapsed Time = {int(time.time() - st_time)} seconds")
            frappe.db.commit()
            time.sleep(1)
    tot_time = int(time.time() - st_time)
    print(f"Total Edits Made = {edits}")
    print(f"Total Time Taken = {tot_time} seconds")
