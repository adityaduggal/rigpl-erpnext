# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from frappe.utils import today, flt
from ..doctype.process_sheet.process_sheet import update_priority
from ...utils.process_sheet_utils import make_jc_for_process_sheet, update_process_sheet_quantities
from ...utils.manufacturing_utils import get_qty_to_manufacture, get_quantities_for_item

from frappe.utils.background_jobs import enqueue


def enqueue_process_sheet_update():
    enqueue(execute, queue="long", timeout=1500)

def execute():
    st_time = time.time()
    create_new_process_sheets()
    frappe.db.commit()
    update_process_sheet_priority()
    frappe.db.commit()
    update_process_sheet_status()
    total_time = int(time.time() - st_time)
    print(f"Total Time taken = {total_time} seconds")


def update_process_sheet_priority():
    st_time = time.time()
    ps_list = frappe.db.sql("""SELECT name, docstatus FROM `tabProcess Sheet` WHERE docstatus < 2 AND status != 'Completed' 
    AND status != 'Short Closed' AND status != 'Stopped'""", as_dict=1)
    for ps in ps_list:
        psd = frappe.get_doc("Process Sheet", ps.name)
        itd = frappe.get_doc("Item", psd.production_item)
        update_priority(psd, itd, backend=1)
        if psd.docstatus == 0 and psd.status != "Draft":
            frappe.db.set_value("Process Sheet", psd.name, "status", "Draft")
            print(f"Updated Status for {psd.name} to Draft")
    end_time = int(time.time() - st_time)
    print(f"Total Time for Updating Priority = {end_time} seconds")


def create_new_process_sheets():
    st_time = time.time()
    value = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "auto_process_sheet_value"))
    if value == 0:
        value = 10000
    # Check items in Warehouses in Production without Job Cards
    it_dict = frappe.db.sql("""SELECT name FROM `tabItem` WHERE disabled = 0 
    AND include_item_in_manufacturing = 1 AND has_variants = 0 AND variant_of IS NOT NULL ORDER BY name""", as_dict=1)
    created = 0
    for it in it_dict:
        it_doc = frappe.get_doc("Item", it.name)
        qty = get_qty_to_manufacture(it_doc)
        qty_dict = get_quantities_for_item(it_doc)
        value_for_manf = qty * qty_dict["valuation_rate"]
        if value_for_manf >= value:
            exiting_ps = frappe.db.sql("""SELECT name FROM `tabProcess Sheet` WHERE docstatus=0 
            AND production_item= '%s'""" % it.name, as_dict=1)
            if exiting_ps:
                ex_ps = frappe.get_doc("Process Sheet", exiting_ps[0].name)
                if ex_ps.quantity < qty:
                    ex_ps.quantity = qty
                    print(f"Updated {ex_ps.name} changed Quantity to {qty} for {it.name}")
                    try:
                        ex_ps.save()
                    except:
                        print(f"Error Encountered while Saving {ex_ps.name} for {it.name}")
            else:
                ps = frappe.new_doc("Process Sheet")
                ps.production_item = it.name
                ps.date = today()
                ps.quantity = qty
                ps.status = "Draft"
                ps.insert()
                print(f"Created {ps.name} for {it.name} for Qty= {qty}")
                created += 1
    it_time = int(time.time() - st_time)
    print(f"Total Process Sheets Created = {created}")
    print(f"Total Time for Creation of Process Sheets = {it_time} seconds")


def update_process_sheet_status():
    st_time = time.time()
    ps_count = 0
    ps_dict = frappe.db.sql("""SELECT name, status, priority FROM `tabProcess Sheet` 
    WHERE docstatus = 1 AND status != 'Completed' AND status != 'Stopped' AND status != 'Short Closed' 
    ORDER BY name""", as_dict=1)
    for ps in ps_dict:
        ps_doc = frappe.get_doc("Process Sheet", ps.name)
        it_doc = frappe.get_doc("Item", ps_doc.production_item)
        make_jc_for_process_sheet(ps_doc)
        update_process_sheet_quantities(ps_doc)
        if ps_doc.short_closed_qty > 0:
            ps_doc.status = "Short Closed"
            print("Short Closed {}".format(ps_doc.name))
        elif ps_doc.quantity <= ps_doc.produced_qty:
            ps_count += 1
            ps_doc.status = "Completed"
            print("Completed {}".format(ps_doc.name))
        else:
            if ps_doc.status == "Submitted":
                for op in ps_doc.operations:
                    if op.completed_qty > 0:
                        ps_count += 1
                        ps_doc.status = "In Progress"
                        print("In Progress Status set for {}".format(ps_doc.name))
        ps_doc.save()
    end_time = time.time()
    tot_ps_time = round(end_time - st_time)
    print(f"Total Process Sheet Status Updated = {ps_count}")
    print(f"Total Time Taken for Process Sheets is {tot_ps_time} seconds")
