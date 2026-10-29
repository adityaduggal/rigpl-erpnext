# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from frappe.utils import cint
from rohit_common.utils.background_doc_processing import enqueue_once
from ...utils.batch_write_utils import bulk_set_values
from ...utils.item_attribute_utils import chunks
from ...utils.lead_time_utils import get_items_lead_time
from ...utils.stock_utils import get_template_max_lead_times


def enqueue_job():
    enqueue_once("rigpl_erpnext.rigpl_erpnext.scheduled_tasks.auto_calculate_lead_times.execute", queue="long", timeout=14400)


def execute():
    """
    Gets all items and calculates the lead times for them from their Purchase Orders or Process
    Sheets. Items without data are then set to the max lead time of the other variants of their
    template which have data, so the max lead time is only based on real data.
    """
    st_time = time.time()
    item_list = frappe.db.sql("""SELECT it.name, it.variant_of,
        IFNULL(rol.warehouse_reorder_level, 0) as rol_qty, it.valuation_rate,
        (IFNULL(rol.warehouse_reorder_level, 0) * it.valuation_rate) as rol_value,
        it.lead_time_days FROM `tabItem` it
        LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent
        AND rol.parentfield = 'reorder_levels' AND rol.parenttype = 'Item'
        WHERE it.has_variants = 0 AND it.disabled = 0 AND it.made_to_order = 0
        AND it.variant_of IS NOT NULL
        ORDER BY rol_value DESC, it.valuation_rate DESC, rol.warehouse_reorder_level DESC,
        it.name""", as_dict=1)
    old_lead_times = {itm.name: itm.lead_time_days for itm in item_list}
    template_of = {itm.name: itm.variant_of for itm in item_list}
    print(f"Total Items to be Checked = {len(old_lead_times)}")
    changes, no_data_items = 0, []
    # Each chunk is read with a fixed number of queries, written in one go and committed
    for chunk in chunks([itm.name for itm in item_list]):
        lead_times = get_items_lead_time(chunk)
        new_lead_times = {}
        for name in chunk:
            avg_days = cint(lead_times[name].avg_days_wt)
            if avg_days == 0:
                no_data_items.append(name)
            elif avg_days != old_lead_times[name]:
                print(f"{name} Lead Time to be Changed from {old_lead_times[name]} to New = "
                    f"{avg_days}")
                new_lead_times[name] = avg_days
        changes += len(bulk_set_values("Item", "lead_time_days", new_lead_times, old_lead_times))
        frappe.db.commit()
        print(f"Committing Changes to Database after {changes}, Total Time Elapsed = "
            f"{int(time.time() - st_time)}")

    max_lead_times = get_template_max_lead_times({template_of[name] for name in no_data_items},
        exclude_items=no_data_items)
    new_lead_times = {}
    for name in no_data_items:
        max_lead_time = cint(max_lead_times.get(template_of[name], 0))
        if max_lead_time != old_lead_times[name]:
            print(f"{name} has no Data so Lead Time Changed based on Maximum Lead Time for "
                f"Template from {old_lead_times[name]} to New = {max_lead_time}")
            new_lead_times[name] = max_lead_time
    changes += len(bulk_set_values("Item", "lead_time_days", new_lead_times, old_lead_times))

    tot_time = int(time.time() - st_time)
    print(f"Total Items Changed = {changes} and Total Time Taken {tot_time} seconds")
