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
    enqueue(execute, queue="long", timeout=21600)


def execute():
    st_time = time.time()
    min_value = 0
    min_rol_value = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "minimum_rol_value"))
    error_items = []
    item_list = frappe.db.sql("""SELECT it.name, IFNULL(rol.warehouse_reorder_level, 0) as rol_qty, it.valuation_rate,
    (IFNULL(rol.warehouse_reorder_level, 0) * it.valuation_rate) as rol_value
    FROM `tabItem` it
    LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent AND rol.parentfield = 'reorder_levels' 
        AND rol.parenttype = 'Item'
    WHERE it.has_variants = 0 AND it.disabled = 0 AND it.made_to_order = 0 AND it.variant_of IS NOT NULL 
    AND (IFNULL(rol.warehouse_reorder_level, 0) * it.valuation_rate) >= %s
    ORDER BY rol_value DESC, it.valuation_rate DESC, rol.warehouse_reorder_level DESC, 
    it.name""" % min_value, as_dict=1)
    sno = 0
    changes = 0
    print(f"Total Items to be Checked = {len(item_list)}")
    for it in item_list:
        sno += 1
        rol = it.rol_qty
        print(f"{sno}. Processing {it.name} with existing ROL= {rol} and Valuation Rate = {it.valuation_rate}")
        itd = frappe.get_doc("Item", it.name)
        changes_made = auto_compute_rol_for_item(itd)
        if changes_made == 1:
            changes += 1
            try:
                itd.save()
            except:
                error_items.append(itd.name)
        # Commit changes to the Database after every 50 item changes
        if changes % 50 == 0 and changes > 0:
            frappe.db.commit()
            print(f"Committing Changes to Database after {changes}, Total Time Elapsed = {int(time.time() - st_time)}")
            time.sleep(2)

    if error_items:
        print(f"Unable to save \n\n {error_items}")

    tot_time = int(time.time() - st_time)
    print(f"Total Time Taken {tot_time} seconds")
