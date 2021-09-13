# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from ...utils.sales_utils import get_total_pending_so_item
from ...utils.stock_utils import get_consolidate_bin
from ...utils.manufacturing_utils import get_planned_qty
from frappe.utils import flt
from frappe.utils.background_jobs import enqueue


def enqueue_ex():
    enqueue(execute, queue="long", timeout=1500)


def execute():
    st_time = time.time()
    it_list = frappe.db.sql("""SELECT it.name, bn.reserved_qty, bn.planned_qty
        FROM `tabItem` it, `tabBin` bn
        WHERE it.disabled = 0 AND it.made_to_order = 0 AND bn.item_code = it.name
        AND it.is_stock_item = 1 AND it.has_variants = 0 AND (bn.reserved_qty > 0 or
        bn.planned_qty > 0)
        GROUP BY it.name
        ORDER BY bn.reserved_qty DESC, bn.planned_qty DESC, it.name ASC""", as_dict=1)
    sno = 0
    print(f"Total Items to be Checked = {len(it_list)}")
    for it in it_list:
        sno += 1
        pending_so_dict = get_total_pending_so_item(it.name)
        bin_data = get_consolidate_bin(it.name)
        plan_data = get_planned_qty(it.name)
        if flt(plan_data.planned) != flt(bin_data[0].planned):
            bin_name = frappe.db.sql("""SELECT name FROM `tabBin` WHERE item_code = '%s'
            AND planned_qty = %s""" % (it.name, bin_data[0].planned), as_list=1)
            if bin_name:
                print(f"{it.name} Planned Data {plan_data.planned} But BIN Data "
                    f"{bin_data[0].planned}")
                frappe.db.set_value("Bin", bin_name[0][0], "planned_qty", plan_data.planned)
            else:
                print(f"{it.name} BIN Missing")
        elif flt(bin_data[0].on_so) != flt(pending_so_dict[0].pending_qty):
            bin_name = frappe.db.sql("""SELECT name FROM `tabBin` WHERE item_code = '%s'
            AND reserved_qty = %s""" % (it.name, bin_data[0].on_so), as_list=1)
            if bin_name:
                print(f"For {it.name} Values on SO {pending_so_dict[0].pending_qty} whereas on "
                    f"BIN {bin_data[0].on_so}")
                frappe.db.set_value("Bin", bin_name[0][0], "reserved_qty", pending_so_dict[0].pending_qty)
            else:
                print(f"For {it.name} Values on SO {pending_so_dict[0].pending_qty} whereas NO BIN")
    tot_time = int(time.time() - st_time)
    print(f"Total Item Checked = {sno} and Total Time for Checking Item Values = {tot_time} seconds")
