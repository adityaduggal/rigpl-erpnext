# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import time
import frappe
from ...utils.job_card_utils import check_existing_job_card
from ...utils.manufacturing_utils import get_comp_qty_operation


def execute():
    st_time = time.time()

    # Update the Total Completed Quantity in Process Sheet Operations and Delete Extra JCR
    ps_op = frappe.db.sql("""SELECT ps.name, pop.name as op_id, pop.completed_qty, pop.idx, pop.allow_consumption_of_rm,
    pop.planned_qty
    FROM `tabProcess Sheet` ps, `tabBOM Operation` pop
    WHERE pop.parenttype = 'Process Sheet' AND pop.parent = ps.name AND pop.planned_qty > pop.completed_qty AND
    pop.status != 'Stopped' AND pop.status != 'Short Closed' AND pop.status != 'Obsolete' 
    AND ps.status != 'Short Closed' AND ps.status != 'Stopped' AND ps.docstatus = 1 
    ORDER BY ps.name, pop.idx""", as_dict=1)
    wrong_pop = 0
    for ps in ps_op:
        calc_comp_qty = get_comp_qty_operation(ps.op_id)
        if calc_comp_qty != ps.completed_qty:
            wrong_pop += 1
            frappe.db.set_value("BOM Operation", ps.op_id, "completed_qty", calc_comp_qty)
            if calc_comp_qty >= ps.planned_qty:
                frappe.db.set_value("BOM Operation", ps.op_id, "status", "Completed")
            print(f"For {ps.name} Row# {ps.idx} Changed the Completed Qty from {ps.completed_qty} to {calc_comp_qty}")
    print(f"Total Wrong PS Operations = {wrong_pop} out of Total {len(ps_op)} and Total Time "
          f"Taken = {int(time.time() - st_time)} seconds")

    draft_jc = frappe.db.sql("""SELECT name, production_item, sales_order_item, operation, operation_id, process_sheet
    FROM `tabProcess Job Card RIGPL` WHERE docstatus=0 ORDER BY name""", as_dict=1)
    delete_jc = 0
    for jc in draft_jc:
        # print("Processing Job Card # {} for Item Code {}".format(jc.name, jc.production_item))
        pend_qty = frappe.db.sql("""SELECT (planned_qty - completed_qty) as pend_qty FROM `tabBOM Operation` WHERE 
        name = '%s' AND parent = '%s' AND parenttype = 'Process Sheet'""" %
                                 (jc.operation_id, jc.process_sheet), as_dict=1)[0].pend_qty
        if pend_qty <= 0:
            delete_jc += 1
            frappe.delete_doc("Process Job Card RIGPL", jc.name, for_reload=True)
            print("Deleted Job Card = {}".format(jc.name))
        existing_jc = check_existing_job_card(item_name=jc.production_item, so_detail=jc.sales_order_item,
                                              operation=jc.operation)
        if existing_jc:
            for oth_jc in existing_jc:
                if oth_jc.name != jc.name:
                    delete_jc += 1
                    frappe.delete_doc("Process Job Card RIGPL", oth_jc.name, for_reload=True)
                    print("Deleted Job Card = {}".format(oth_jc.name))
                    removed_jc = next(jc for jc in draft_jc if jc["name"] == oth_jc.name)
                    draft_jc.remove(removed_jc)
    print(f"Total Job Cards to be Deleted = {delete_jc} and Total Time Taken = {int(time.time() - st_time)} seconds")
