# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from ...utils.sales_utils import get_total_pending_so_item
from ...utils.purchase_utils import get_po_pend_qty
from ...utils.stock_utils import get_consolidate_bin, get_indented_qty
from ...utils.manufacturing_utils import get_planned_qty, get_qty_for_prod_for_item
from frappe.utils import flt
from frappe.utils.background_jobs import enqueue


def enqueue_ex():
    enqueue(execute, queue="long", timeout=1500)


def execute():
    st_time = time.time()
    get_wrong_projected()
    error_items = []
    it_list = frappe.db.sql("""SELECT it.name, bn.reserved_qty, bn.planned_qty,
        bn.reserved_qty_for_production, bn.indented_qty, bn.ordered_qty
        FROM `tabItem` it, `tabBin` bn
        WHERE it.disabled = 0 AND it.made_to_order = 0 AND bn.item_code = it.name
        AND it.is_stock_item = 1 AND it.has_variants = 0 AND (bn.reserved_qty > 0 OR
        bn.planned_qty > 0 OR bn.reserved_qty_for_production > 0 OR bn.indented_qty > 0 OR
        bn.ordered_qty > 0)
        GROUP BY it.name
        ORDER BY bn.reserved_qty DESC, bn.planned_qty DESC, bn.reserved_qty_for_production DESC,
        it.name ASC""", as_dict=1)
    sno, wrong_bin = 0, 0
    print(f"Total Items to be Checked = {len(it_list)}")
    time.sleep(1)
    for itm in it_list:
        sno += 1
        bin_d = get_consolidate_bin(itm.name)
        b_so, b_po, b_ind, b_plan, b_prd = bin_d[0].on_so, bin_d[0].on_po, bin_d[0].on_indent, \
            bin_d[0].planned, bin_d[0].for_prd
        act_soq = flt(get_total_pending_so_item(itm.name)[0].pending_qty)
        act_planq = flt(get_planned_qty(itm.name).planned)
        act_prdq = get_qty_for_prod_for_item(itm.name)
        act_indq = get_indented_qty(itm.name)
        act_poq = get_po_pend_qty(itm.name)
        if b_so != act_soq:
            wrong_bin += 1
            error_items = update_bin_data(itm.name, "reserved_qty", b_so, act_soq, error_items)
        elif b_po != act_poq:
            wrong_bin += 1
            error_items = update_bin_data(itm.name, "ordered_qty", b_po, act_poq, error_items)
        elif b_ind != act_indq:
            wrong_bin += 1
            error_items = update_bin_data(itm.name, "indented_qty", b_ind, act_indq, error_items)
        elif b_plan != act_planq:
            wrong_bin += 1
            error_items = update_bin_data(itm.name, "planned_qty", b_plan, act_planq, error_items)
        elif b_prd != act_prdq:
            wrong_bin += 1
            error_items = update_bin_data(itm.name, "reserved_qty_for_production", b_prd,
                act_prdq, error_items)

    tot_time = int(time.time() - st_time)
    print(f"Total Item Checked = {sno} and Wrong Bins = {wrong_bin} Total Time for Checking "
        f"Item Values = {tot_time} seconds")
    if error_items:
        print(f"Error while saving these Bins for Item Code \n {error_items}")


def get_wrong_projected():
    wrong_projected = frappe.db.sql("""SELECT name, projected_qty, (actual_qty + ordered_qty +
        indented_qty + planned_qty - reserved_qty - reserved_qty_for_production -
        reserved_qty_for_sub_contract) as calc_proj FROM `tabBin`
        WHERE projected_qty != (actual_qty + ordered_qty +
        indented_qty + planned_qty - reserved_qty - reserved_qty_for_production -
        reserved_qty_for_sub_contract)""", as_dict=1)
    for bnd in wrong_projected:
        print(f"Found {bnd.name} with Current Projected = {bnd.projected_qty} but Actual "
            f"Projected = {bnd.calc_proj}")
        bndoc = frappe.get_doc("Bin", bnd.name)
        bndoc.save()

def update_bin_data(item_code, field, bin_qty, act_qty, error_list):
    bin_name = frappe.db.sql(f"""SELECT name FROM `tabBin` WHERE item_code = '{item_code}'
        AND {field} = {bin_qty}""", as_dict=1)
    if bin_name:
        print(f"For {item_code} Values {field} should be {act_qty} whereas on "
                    f"BIN {bin_qty}")
        bndoc = frappe.get_doc("Bin", bin_name[0].name)
        setattr(bndoc, field, act_qty)
        bndoc.save()
    else:
        error_list.append(item_code)
        print(f"For {item_code} Actual Values for {field} = {act_qty} whereas there is NO BIN")
    return error_list
