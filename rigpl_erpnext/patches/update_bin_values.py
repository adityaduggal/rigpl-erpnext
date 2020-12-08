# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from ..utils.sales_utils import get_total_pending_so_item
from ..utils.stock_utils import get_consolidate_bin
from ..utils.manufacturing_utils import get_planned_qty
from frappe.utils import flt


def execute():
    st_time = time.time()
    it_list = frappe.db.sql("""SELECT name FROM `tabItem` WHERE disabled=0 AND made_to_order = 0 
    AND is_stock_item = 1""", as_dict=1)
    for it in it_list:
        pending_so_dict = get_total_pending_so_item(it.name)
        bin_data = get_consolidate_bin(it.name)
        plan_data = get_planned_qty(it.name)
        if plan_data.planned > 0:
            if bin_data:
                if bin_data[0].planned == plan_data.planned:
                    pass
                else:
                    print(f"{it.name} Planned Data {plan_data.planned} But BIN Data {bin_data[0].planned}")
                    bin_name = frappe.db.sql("""SELECT name FROM `tabBin` WHERE item_code = '%s' 
                    AND planned_qty = %s""" % (it.name, bin_data[0].planned), as_list=1)
                    if bin_name:
                        frappe.db.set_value("Bin", bin_name[0][0], "planned_qty", plan_data.planned)
            else:
                print(f"{it.name} BIN Missing")
        if bin_data and flt(bin_data[0].planned) > 0:
            if plan_data.planned != bin_data[0].planned:
                print(f"{it.name} Planned Data {plan_data.planned} But BIN Data {bin_data[0].planned} from BIN")

        if pending_so_dict and pending_so_dict[0].pending_qty > 0:
            if bin_data and bin_data[0].on_so == pending_so_dict[0].pending_qty:
                pass
            else:
                if bin_data:
                    print(f"For {it.name} Values on SO {pending_so_dict[0].pending_qty} whereas on "
                          f"BIN {bin_data[0].on_so}")
                    bin_name = frappe.db.sql("""SELECT name FROM `tabBin` WHERE item_code = '%s' 
                    AND reserved_qty = %s""" % (it.name, bin_data[0].on_so), as_list=1)
                    if bin_name:
                        frappe.db.set_value("Bin", bin_name[0][0], "reserved_qty", pending_so_dict[0].pending_qty)
                else:
                    print(f"For {it.name} Values on SO {pending_so_dict[0].pending_qty} whereas NO BIN")
        if bin_data and flt(bin_data[0].on_so) > 0:
            if pending_so_dict and pending_so_dict[0].pending_qty == bin_data[0].on_so:
                pass
            else:
                if pending_so_dict:
                    print(f"For {it.name} BIN data on SO = {bin_data[0].on_so} whereas Pending SO = "
                          f"{pending_so_dict[0].pending_qty}")
                else:
                    print(f"For {it.name} BIN data on SO = {bin_data[0].on_so} whereas NO Pending SO Data")
                    bin_name = frappe.db.sql("""SELECT name FROM `tabBin` WHERE item_code = '%s' 
                    AND reserved_qty > 0 """ % it.name, as_list=1)
                    if bin_name:
                        frappe.db.set_value("Bin", bin_name[0][0], "reserved_qty", 0)
    tot_time = int(time.time() - st_time)
    print(f"Total Time for Checking Item Values = {tot_time} seconds")
