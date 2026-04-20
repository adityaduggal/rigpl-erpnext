# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from ...utils.sales_utils import get_total_pending_so_item
from ...utils.purchase_utils import get_po_pend_qty
from ...utils.stock_utils import get_consolidate_bin, get_indented_qty
from rigpl_erpnext.manufacturing_rigpl.utils.manufacturing_utils import get_planned_qty, get_qty_for_prod_for_item
from frappe.utils import flt
from frappe.utils.background_jobs import enqueue


def enqueue_ex():
    enqueue(execute, queue="long", timeout=1500)


def execute():
    st_time = time.time()
    get_wrong_projected()
    error_items = []
    
    # 1. Fetch items that actually have bin numbers worth checking
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
        
    # Optimizations: Load bulk maps
    bin_agg = frappe.db.sql("""SELECT item_code, SUM(reserved_qty) as on_so,
        SUM(ordered_qty) as on_po, SUM(indented_qty) as on_indent,
        SUM(planned_qty) as planned, SUM(reserved_qty_for_production) as for_prd
        FROM `tabBin` GROUP BY item_code""", as_dict=1)
    bin_map = {d.item_code: d for d in bin_agg}

    so_agg = frappe.db.sql("""SELECT sod.item_code, SUM(sod.qty - sod.delivered_qty) as pending_qty
        FROM `tabSales Order` so, `tabSales Order Item` sod
        WHERE so.name = sod.parent AND so.docstatus = 1 AND so.status != 'Closed'
        AND sod.qty > sod.delivered_qty GROUP BY sod.item_code""", as_dict=1)
    so_map = {d.item_code: flt(d.pending_qty) for d in so_agg}

    po_agg = frappe.db.sql("""SELECT pod.item_code, SUM(pod.qty - pod.received_qty) as poq
        FROM `tabPurchase Order` po, `tabPurchase Order Item` pod
        WHERE po.docstatus = 1 AND po.status != 'Closed' AND pod.received_qty < pod.qty
        AND pod.parent = po.name GROUP BY pod.item_code""", as_dict=1)
    po_map = {d.item_code: flt(d.poq) for d in po_agg}

    ind_agg = frappe.db.sql("""SELECT mri.item_code, SUM(mri.qty - mri.ordered_qty) as ind_qty
        FROM `tabMaterial Request` mr, `tabMaterial Request Item` mri
        WHERE mri.parent = mr.name AND mr.docstatus = 1 AND mr.status != 'Stopped'
        AND mri.qty > mri.ordered_qty GROUP BY mri.item_code""", as_dict=1)
    ind_map = {d.item_code: flt(d.ind_qty) for d in ind_agg}

    wo_agg = frappe.db.sql("""SELECT production_item, SUM(qty - produced_qty) as wo_plan 
        FROM `tabWork Order`
        WHERE docstatus = 1 AND status != 'Stopped' GROUP BY production_item""", as_dict=1)
    ps_agg = frappe.db.sql("""SELECT production_item, SUM(quantity - produced_qty) as ps_plan
        FROM `tabProcess Sheet` WHERE docstatus = 1 AND status NOT IN ('Short Closed', 'Stopped', 'Completed') 
        GROUP BY production_item""", as_dict=1)
    plan_map = {}
    for d in wo_agg:
        plan_map[d.production_item] = plan_map.get(d.production_item, 0) + flt(d.wo_plan)
    for d in ps_agg:
        plan_map[d.production_item] = plan_map.get(d.production_item, 0) + flt(d.ps_plan)

    prd_agg = frappe.db.sql("""SELECT psi.item_code, SUM(psi.calculated_qty - psi.qty) as qty_prod
        FROM `tabProcess Sheet Items` psi, `tabProcess Sheet` ps
        WHERE ps.name = psi.parent AND psi.parenttype = 'Process Sheet' AND ps.docstatus = 1
        AND psi.parentfield = 'rm_consumed' AND ps.status NOT IN ("Stopped", "Completed", "Short Closed")
        AND psi.donot_consider_rm_for_production != 1
        GROUP BY psi.item_code""", as_dict=1)
    prd_map = {d.item_code: flt(d.qty_prod) for d in prd_agg}
    
    sno, wrong_bin = 0, 0
    print(f"Total Items to be Checked = {len(it_list)}")
    time.sleep(1)
    for itm in it_list:
        sno += 1
        bd = bin_map.get(itm.name, {})
        b_so, b_po, b_ind, b_plan, b_prd = bd.get('on_so', 0), bd.get('on_po', 0), bd.get('on_indent', 0), bd.get('planned', 0), bd.get('for_prd', 0)
        
        act_soq = so_map.get(itm.name, 0.0)
        act_planq = plan_map.get(itm.name, 0.0)
        act_prdq = prd_map.get(itm.name, 0.0)
        act_indq = ind_map.get(itm.name, 0.0)
        act_poq = po_map.get(itm.name, 0.0)
        
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
