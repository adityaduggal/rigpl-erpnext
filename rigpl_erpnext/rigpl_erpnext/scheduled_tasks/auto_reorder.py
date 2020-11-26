# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
from frappe.utils import flt
from frappe.utils.background_jobs import enqueue
from ...utils.stock_utils import auto_compute_rol_for_item


def enqueue_rol_job():
    enqueue("rigpl_erpnext.rigpl_erpnext.scheduled_tasks.auto_reorder.execute", queue="background", timeout=21600)


def execute():
    st_time = time.time()
    """
    ROL should never change Drastically. Definition of Drastic = Change should not be more than 10~20% or for small
    or non-existent ROL then new ROL the change shud nt b more than 10000 or auto_process_sheet_value in RIGPL settings
    """
    error_items = []
    item_list = frappe.db.sql("""SELECT it.name, IFNULL(rol.warehouse_reorder_level, 0) as rol_qty
    FROM `tabItem` it
    LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent AND rol.parentfield = 'reorder_levels'
        AND rol.parenttype = 'Item'
    WHERE it.has_variants = 0 AND it.disabled = 0 
    AND it.made_to_order = 0 AND it.variant_of IS NOT NULL
    ORDER BY rol.warehouse_reorder_level DESC, it.name""", as_dict=1)
    sno = 0
    for it in item_list:
        sno += 1
        itd = frappe.get_doc("Item", it.name)
        rol_list = frappe.db.sql("""SELECT warehouse_reorder_level as rol FROM `tabItem Reorder` WHERE parent = '%s' AND 
        parenttype = 'Item' AND parentfield = 'reorder_levels'""" % it.name, as_dict=1)
        if rol_list:
            rol = flt(rol_list[0].rol)
        else:
            rol = 0
        print(f"Processing {it.name} with existing ROL= {rol} and Valuation Rate = {itd.valuation_rate}")
        auto_compute_rol_for_item(itd)
        try:
            itd.save()
        except:
            error_items.append(itd.name)
        # Commit changes to the Database after every 50 items
        if sno % 50 == 0 and sno > 0:
            frappe.db.commit()
            print(f"Committing Changes to Database after {sno}")

    if error_items:
        print(f"Unable to save \n\n {error_items}")


    tot_time = int(time.time() - st_time)
    print(f"Total Time Taken {tot_time} seconds")
