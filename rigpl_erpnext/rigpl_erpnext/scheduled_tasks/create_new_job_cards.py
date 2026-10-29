# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
"Clean up Job Cards" step of the manufacturing pipeline (#147). Short closes the draft Job Cards
whose Sales Order Item is delivered or closed, and deletes the Job Cards without a Sales Order
that still have a zero qty after a save. Job Cards with an open Sales Order are left to "Update
Job Card Status", which recalculates their quantities with batched reads.
"""
from __future__ import unicode_literals
import time
import frappe
from ...manufacturing_rigpl.utils.batch_qty_utils import get_open_so_items
from .process_sheet_update import run_write

JC_DOCTYPE = "Process Job Card RIGPL"


def execute():
    st_time = time.time()
    job_cards = frappe.get_all(JC_DOCTYPE, filters={"docstatus": 0},
        or_filters={"priority": 999, "total_qty": 0, "for_quantity": 0},
        fields=["name", "sales_order_item", "total_qty", "for_quantity"], order_by="creation, name")
    print(f"Total No of Job Cards with 999 Priority or ZERO Total Qty OR ZERO FOR QTY = "
        f"{len(job_cards)}")
    open_so_items = get_open_so_items([jc.sales_order_item for jc in job_cards if jc.sales_order_item])
    sc_jcr, changed_jcr, deleted_jcr = 0, 0, 0
    for jc in job_cards:
        if jc.sales_order_item:
            if jc.sales_order_item not in open_so_items:
                sc_jcr += short_close(jc.name)
        elif jc.total_qty == 0 or jc.for_quantity == 0:
            saved, deleted = save_or_delete(jc.name)
            changed_jcr += saved
            deleted_jcr += deleted
    print(f"Total No of Job Cards Deleted = {deleted_jcr}")
    print(f"Total No of Job Cards Short Closed = {sc_jcr}")
    print(f"Total No of Job Cards Updated = {changed_jcr}")
    print(f"Total Time Taken for Cleaning up Job Cards = {int(time.time() - st_time)} seconds")


def short_close(name):
    """Submits the Job Card as short closed without a Stock Entry. Returns 1 when it worked."""
    def write():
        jcd = frappe.get_doc(JC_DOCTYPE, name)
        jcd.no_stock_entry = 1
        jcd.short_close_operation = 1
        jcd.submit()

    return int(run_write("jc_cleanup", write, f"Job Card {name} not short closed"))


def save_or_delete(name):
    """
    Saves the Job Card so that validate recalculates its quantities, and deletes it when a
    quantity is still zero. Returns (saved, deleted) as 0 or 1.
    """
    jcd = frappe.get_doc(JC_DOCTYPE, name)
    if not run_write("jc_cleanup", jcd.save, f"Job Card {name} for Process Sheet {jcd.process_sheet} not saved"):
        return 0, 0
    if jcd.total_qty and jcd.for_quantity:
        return 1, 0
    print(f"Deleting {name} as ZERO Total Qty or For Quantity is ZERO")
    deleted = run_write("jc_cleanup", lambda: frappe.delete_doc(JC_DOCTYPE, name, for_reload=True),
        f"Job Card {name} not deleted")
    return 1, int(deleted)
