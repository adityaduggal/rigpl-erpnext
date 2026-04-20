# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
from frappe.utils import flt
from frappe.utils.background_jobs import enqueue
from ...utils.lead_time_utils import get_item_lead_time
from ...utils.stock_utils import get_max_lead_times


def enqueue_job():
    enqueue(execute, queue="long", timeout=14400)


def execute():
    """
    Gets all items and calculates the lead times for them if lead time is zero then set to zero
    Once all items are completed get another list of items where lead time is ZERO only and
    then set to max lead time for that template this ways the max lead time is only based on real
    data.
    """
    st_time = time.time()
    error_items = []
    item_list = frappe.db.sql("""SELECT it.name, IFNULL(rol.warehouse_reorder_level, 0) as rol_qty,
        it.valuation_rate,
        (IFNULL(rol.warehouse_reorder_level, 0) * it.valuation_rate) as rol_value,
        it.lead_time_days FROM `tabItem` it
        LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent
        AND rol.parentfield = 'reorder_levels' AND rol.parenttype = 'Item'
        WHERE it.has_variants = 0 AND it.disabled = 0 AND it.made_to_order = 0
        AND it.variant_of IS NOT NULL
        ORDER BY rol_value DESC, it.valuation_rate DESC, rol.warehouse_reorder_level DESC,
        it.name""", as_dict=1)
    
    sno = 0
    changes = 0
    BATCH_SIZE = 500
    
    frappe.logger("auto_calculate_lead_times").info(f"Total Items to be Checked = {len(item_list)}")
    print(f"Total Items to be Checked = {len(item_list)}")
    
    for itm in item_list:
        sno += 1
        print(f"{sno}. Processing {itm.name} with existing Lead Days= {itm.lead_time_days}")
        
        try:
            ldt_dict = get_item_lead_time(itm.name)
            new_lead_time = ldt_dict.avg_days_wt
            
            if new_lead_time != itm.lead_time_days and new_lead_time != 0:
                print(f"{itm.name} Lead Time to be Changed from {itm.lead_time_days} to New = {new_lead_time}")
                frappe.db.set_value("Item", itm.name, "lead_time_days", new_lead_time)
                changes += 1
            elif new_lead_time < 2 and itm.lead_time_days != 0:
                print(f"{itm.name} Lead Time being Set to Zero since no Data received")
                frappe.db.set_value("Item", itm.name, "lead_time_days", 0)
                changes += 1
                
            if changes > 0 and changes % BATCH_SIZE == 0:
                frappe.db.commit()
                print(f"Committing Changes to Database after {changes}, Total Time Elapsed = {int(time.time() - st_time)}")
        except Exception as excp:
            print(f"Error Occurred while Processing {itm.name} and Error = {excp}")
            error_items.append(itm.name)
            
    frappe.db.commit()

    zero_ld_items = frappe.db.sql("""SELECT it.name, it.lead_time_days, it.variant_of
        FROM `tabItem` it
        WHERE it.has_variants = 0 AND it.disabled = 0 AND it.made_to_order = 0
        AND it.variant_of IS NOT NULL AND it.lead_time_days < 2""", as_dict=1)
        
    # Bulk Map template max lead times
    templates = list(set([d.variant_of for d in zero_ld_items]))
    template_lead_times = {}
    if templates:
        max_ld_sql = frappe.db.sql("""SELECT variant_of, MAX(lead_time_days) as max_lead_time 
            FROM `tabItem` 
            WHERE variant_of IN %s AND disabled = 0 
            GROUP BY variant_of""", (tuple(templates),), as_dict=1)
        for d in max_ld_sql:
            template_lead_times[d.variant_of] = flt(d.max_lead_time)

    for itm in zero_ld_items:
        max_lead_times = template_lead_times.get(itm.variant_of, 0.0)
        if max_lead_times != itm.lead_time_days:
            print(f"{itm.name} Lead Time to be Changed based on Maximum Lead Time for Template "
                f"from {itm.lead_time_days} to New = {max_lead_times}")
            try:
                # Bug Fix: Update to max_lead_times instead of 0
                frappe.db.set_value("Item", itm.name, "lead_time_days", max_lead_times)
                changes += 1
                if changes > 0 and changes % BATCH_SIZE == 0:
                    frappe.db.commit()
            except Exception as excp:
                print(f"Error Occurred while Saving {itm.name} and Error = {excp}")
                error_items.append(itm.name)

    frappe.db.commit()
    if error_items:
        print(f"Unable to save \n\n {error_items}")

    tot_time = int(time.time() - st_time)
    print(f"Total Items Changed = {changes} and Total Time Taken {tot_time} seconds")
