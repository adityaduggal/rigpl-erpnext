# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
from frappe.utils import flt
from frappe.utils.background_jobs import enqueue
from ...utils.stock_utils import get_item_lead_time, get_max_lead_times


def enqueue_job():
    enqueue(execute, queue="long", timeout=14400)


def execute():
    st_time = time.time()
    error_items = []
    item_list = frappe.db.sql("""SELECT it.name, IFNULL(rol.warehouse_reorder_level, 0) as rol_qty,
        it.valuation_rate,
        (IFNULL(rol.warehouse_reorder_level, 0) * it.valuation_rate) as rol_value,
        it.lead_time_days FROM `tabItem` it
        LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent
        AND rol.parentfield = 'reorder_levels' AND rol.parenttype = 'Item'
        WHERE it.has_variants = 0 AND it.disabled = 0 AND it.made_to_order = 0
        AND it.variant_of IS NOT NULL AND it.name = 'CX3XP3002W7'
        ORDER BY rol_value ASC, it.valuation_rate DESC, rol.warehouse_reorder_level ASC,
        it.name""", as_dict=1)
    sno, changes, old_changes = 0, 0,0
    print(f"Total Items to be Checked = {len(item_list)}")
    for itm in item_list:
        sno += 1
        print(f"{sno}. Processing {itm.name} with existing Lead Days= {itm.lead_time_days}")
        ldt_dict = get_item_lead_time(itm.name)
        if ldt_dict.avg_days_wt != itm.lead_time_days and ldt_dict.avg_days_wt != 0:
            itd = frappe.get_doc("Item", itm.name)
            print(f"{itm.name} Lead Time to be Changed from {itd.lead_time_days} to New = "
                f"{ldt_dict.avg_days_wt}")
            changes += 1
            try:
                itd.lead_time_days = ldt_dict.avg_days_wt
                itd.save()
            except Exception as excp:
                print(f"Error Occurred while Saving {itm.name} and Error = {excp}")
                error_items.append(itd.name)
        elif ldt_dict.avg_days_wt == 0:
            max_lead_times = get_max_lead_times(itm.name)
            if max_lead_times != itm.lead_time_days:
                itd = frappe.get_doc("Item", itm.name)
                print(f"{itm.name} Lead Time to be Changed based on Maximum Lead Time for Template "
                    f"from {itd.lead_time_days} to New = {max_lead_times}")
                try:
                    itd.lead_time_days = max_lead_times
                    itd.save()
                except Exception as excp:
                    print(f"Error Occurred while Saving {itm.name} and Error = {excp}")
                    error_items.append(itd.name)
        # Commit changes to the Database after every 50 item changes
        if changes % 50 == 0 and changes > 0 and changes != old_changes:
            old_changes = changes
            frappe.db.commit()
            print(f"Committing Changes to Database after {changes}, Total Time Elapsed = "
            f"{int(time.time() - st_time)}")
            time.sleep(2)
    if error_items:
        print(f"Unable to save \n\n {error_items}")

    tot_time = int(time.time() - st_time)
    print(f"Total Items Changed = {changes} and Total Time Taken {tot_time} seconds")
