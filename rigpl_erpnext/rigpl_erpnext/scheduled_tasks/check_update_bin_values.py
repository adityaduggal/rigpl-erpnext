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


def execute():
    st_time = time.time()
    it_list = frappe.db.sql("""SELECT name FROM `tabItem` WHERE disabled=0 AND made_to_order = 0 
    AND is_stock_item = 1 AND has_variants = 0""", as_dict=1)
    sno = 0
    for it in it_list:
        sno += 1
        pending_so_dict = get_total_pending_so_item(it.name)
        bin_data = get_consolidate_bin(it.name)
        plan_data = get_planned_qty(it.name)
        if flt(plan_data.planned) != flt(bin_data[0].planned):
            print(f"{it.name} Planned Data {plan_data.planned} But BIN Data {bin_data[0].planned}")
            bin_name = frappe.db.sql("""SELECT name FROM `tabBin` WHERE item_code = '%s' 
            AND planned_qty = %s""" % (it.name, bin_data[0].planned), as_list=1)
            if bin_name:
                frappe.db.set_value("Bin", bin_name[0][0], "planned_qty", plan_data.planned)
            else:
                print(f"{it.name} BIN Missing")

        if flt(bin_data[0].on_so) != flt(pending_so_dict[0].pending_qty):
            print(f"For {it.name} Values on SO {pending_so_dict[0].pending_qty} whereas on "
                  f"BIN {bin_data[0].on_so}")
            bin_name = frappe.db.sql("""SELECT name FROM `tabBin` WHERE item_code = '%s' 
            AND reserved_qty = %s""" % (it.name, bin_data[0].on_so), as_list=1)
            if bin_name:
                frappe.db.set_value("Bin", bin_name[0][0], "reserved_qty", pending_so_dict[0].pending_qty)
            else:
                print(f"For {it.name} Values on SO {pending_so_dict[0].pending_qty} whereas NO BIN")
    tot_time = int(time.time() - st_time)
    print(f"Total Item Checked = {sno} and Total Time for Checking Item Values = {tot_time} seconds")