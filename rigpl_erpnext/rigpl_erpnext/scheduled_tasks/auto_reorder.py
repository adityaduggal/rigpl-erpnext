# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import csv
import frappe
import time
from frappe.utils import flt, fmt_money
from rohit_common.utils.background_doc_processing import enqueue_once
from ...utils.item_attribute_utils import chunks
from ...utils.stock_utils import compute_rol_for_items, get_items_for_rol, \
    set_item_reorder_levels


def enqueue_rol_job():
    enqueue_once("rigpl_erpnext.rigpl_erpnext.scheduled_tasks.auto_reorder.execute", queue="long", timeout=21600)


def execute(dry_run=0):
    """
    Sets the Re Order Level of all items which are not made to order. With dry_run nothing is
    written: the old and new ROL of the changed items are saved to rol_preview.csv in the site
    folder and a summary is printed.
    """
    st_time = time.time()
    min_value = 0
    error_items, preview = [], []
    item_list = frappe.db.sql("""SELECT it.name, IFNULL(rol.warehouse_reorder_level, 0) as rol_qty,
    it.valuation_rate, (IFNULL(rol.warehouse_reorder_level, 0) * it.valuation_rate) as rol_value
    FROM `tabItem` it
    LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent AND rol.parentfield = 'reorder_levels'
        AND rol.parenttype = 'Item'
    WHERE it.has_variants = 0 AND it.disabled = 0 AND it.made_to_order = 0
    AND it.variant_of IS NOT NULL
    AND (IFNULL(rol.warehouse_reorder_level, 0) * it.valuation_rate) >= %s
    ORDER BY rol_value DESC, it.valuation_rate DESC, rol.warehouse_reorder_level DESC,
    it.name""", min_value, as_dict=1)
    sno = 0
    changes = 0
    print(f"Total Items to be Checked = {len(item_list)}")
    # Each chunk is read with a fixed number of queries, written in one go and committed
    for chunk in chunks([it.name for it in item_list]):
        items = get_items_for_rol(chunk)
        new_rols = compute_rol_for_items(items)
        item_rols = []
        for itm in items:
            sno += 1
            ex_rol = itm.existing_rol
            new_rol, basis, ch_type = new_rols[itm.name]
            if new_rol != ex_rol:
                if dry_run:
                    preview.append([itm.name, flt(itm.valuation_rate), ex_rol, new_rol,
                        new_rol - ex_rol, flt((new_rol - ex_rol) * itm.valuation_rate), ch_type,
                        basis])
                    continue
                print(f"{sno}. Changing ROL for {itm.name} from {ex_rol} to New ROL= {new_rol} with "
                    f"Value Difference = {fmt_money(int(new_rol - ex_rol) * itm.valuation_rate)} "
                    f"with {ch_type} Type Change Based on {basis}")
                item_rols.append((itm, new_rol))
        if dry_run:
            print(f"Checked {sno} Items, Time Elapsed = {int(time.time() - st_time)}")
            continue
        skipped = set_item_reorder_levels(item_rols)
        error_items += skipped
        changes += len(item_rols) - len(skipped)
        frappe.db.commit()
        print(f"Committing Changes to Database after {changes}, Total Time Elapsed = "
            f"{int(time.time() - st_time)}")

    if dry_run:
        print_rol_preview(preview, len(item_list))
    if error_items:
        print(f"Unable to save Below Items since they have no Default Warehouse:\n\n {error_items}")

    tot_time = int(time.time() - st_time)
    print(f"Total Time Taken {tot_time} seconds")


def print_rol_preview(preview, total_items):
    """
    Saves the ROL changes of a dry run to rol_preview.csv in the site folder and prints a summary
    """
    path = frappe.get_site_path("rol_preview.csv")
    with open(path, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Item", "Valuation Rate", "Old ROL", "New ROL", "Qty Change",
            "Value Change", "Change Type", "Basis"])
        writer.writerows(preview)
    increases = [row for row in preview if row[4] > 0]
    decreases = [row for row in preview if row[4] < 0]
    old_value = sum(row[2] * row[1] for row in preview)
    new_value = sum(row[3] * row[1] for row in preview)
    print(f"\nDRY RUN, nothing is saved. {len(preview)} of {total_items} Items would change: "
        f"{len(increases)} up, {len(decreases)} down. "
        f"ROL Value of these Items {fmt_money(old_value)} -> {fmt_money(new_value)}")
    print("Biggest Value Changes:")
    for row in sorted(preview, key=lambda r: abs(r[5]), reverse=True)[:20]:
        print(f"  {row[0]}: ROL {row[2]} -> {row[3]} ({fmt_money(row[5])}) {row[7]}")
    print(f"All changes are in {path}")
