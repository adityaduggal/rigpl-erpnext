# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
from frappe.utils import flt, fmt_money
from frappe.utils.background_jobs import enqueue
from ...utils.stock_utils import auto_compute_rol_for_item, update_item_rol, \
    get_existing_rol_for_item


def enqueue_rol_job():
    enqueue(execute, queue="long", timeout=21600)


def execute():
    st_time = time.time()
    min_value = 0
    old_changes = 0
    min_rol_value = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "minimum_rol_value"))
    error_items = []
    item_list = frappe.db.sql("""SELECT it.name, IFNULL(rol.warehouse_reorder_level, 0) as rol_qty,
    it.valuation_rate, (IFNULL(rol.warehouse_reorder_level, 0) * it.valuation_rate) as rol_value
    FROM `tabItem` it
    LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent AND rol.parentfield = 'reorder_levels'
        AND rol.parenttype = 'Item'
    WHERE it.has_variants = 0 AND it.disabled = 0 AND it.made_to_order = 0
    AND it.variant_of IS NOT NULL
    AND (IFNULL(rol.warehouse_reorder_level, 0) * it.valuation_rate) >= %s
    ORDER BY rol_value DESC, it.valuation_rate DESC, rol.warehouse_reorder_level DESC,
    it.name""" % min_value, as_dict=1)
    sno = 0
    changes = 0
    print(f"Total Items to be Checked = {len(item_list)}")
    time.sleep(2)
    for it in item_list:
        sno += 1
        rol = it.rol_qty
        print(f"{sno}. Processing {it.name} with existing ROL= {rol} and Valuation Rate = "
            f"{fmt_money(it.valuation_rate)} and Total Value = {fmt_money(rol*it.valuation_rate)}")
        itd = frappe.get_doc("Item", it.name)
        def_wh = frappe.db.sql("""SELECT default_warehouse FROM `tabItem Default`
            WHERE parenttype = 'Item' AND parentfield = 'item_defaults'
            AND parent = '%s'""" % itd.name, as_dict=1)
        ex_rol = get_existing_rol_for_item(it.name)
        new_rol, period, ch_type = auto_compute_rol_for_item(itd)
        if new_rol != ex_rol:
            print(f"Changing ROL for {it.name} from {ex_rol} to New ROL= {new_rol} with Value "
                f"Difference = {fmt_money(int(new_rol - ex_rol) * itd.valuation_rate)} "
                f"with {ch_type} Type Change Based on {period} months Data")
            changes += 1
            try:
                update_item_rol(itd, new_rol)
                itd.save()
            except Exception as excp:
                print(f"Error Occured while Saving Item {it.name} with Error = {excp}")
                error_items.append(itd.name)
        # Commit changes to the Database after every 50 item changes
        if changes % 50 == 0 and changes > 0 and changes != old_changes:
            old_changes = changes
            frappe.db.commit()
            print(f"Committing Changes to Database after {changes}, Total Time Elapsed = "
                f"{int(time.time() - st_time)}")
            time.sleep(2)

    if error_items:
        print(f"Unable to save Below Items:\n\n {error_items}")

    tot_time = int(time.time() - st_time)
    print(f"Total Time Taken {tot_time} seconds")
