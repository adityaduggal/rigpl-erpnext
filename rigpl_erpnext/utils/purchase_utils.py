# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from .other_utils import auto_round_up, get_base_doc, get_weighted_average


def get_purchase_lead_times(item_name, frm_dt=None, to_dt=None):
    """
    Returns a dict with item_name and lead_times based on Purchase Orders to GRN times
    Lead Time Dict would have following keys: item_name, avg_days, no_of_trans, total_qty
    min_days, max_days, avg_days_wt, tot_qty
    avg_days_wt is the weighted average delivery time
    """
    day_wise = []
    ldt_dict = frappe._dict({})
    ldt_dict["item_name"] = item_name
    po_dict = get_po_for_item(item_name, frm_dt=frm_dt, to_dt=to_dt)
    ldt_dict["no_of_trans"] = len(po_dict)
    for pod in po_dict:
        avg_days = get_avg_days_for_po(pod)
        if ldt_dict.get("min_days", 0) == 0:
            ldt_dict["min_days"] = avg_days.avg_days
        else:
            if ldt_dict["min_days"] > avg_days.avg_days:
                ldt_dict["min_days"] = avg_days.avg_days
        if ldt_dict.get("max_days", 0) == 0:
            ldt_dict["max_days"] = avg_days.avg_days
        else:
            if ldt_dict["max_days"] < avg_days.avg_days:
                ldt_dict["max_days"] = avg_days.avg_days
        day_wise.append(get_avg_days_for_po(pod).copy())
    avg_days_wt, tot_qty = get_weighted_average(list_of_data=day_wise, avg_key="avg_days",
        wt_key="tot_qty")
    ldt_dict["avg_days_wt"] = avg_days_wt
    ldt_dict["tot_qty"] = tot_qty
    return ldt_dict


def get_po_for_item(it_name, frm_dt=None, to_dt=None):
    cond = ""
    if frm_dt:
        cond += " AND po.creation >= '%s'" % frm_dt
    if to_dt:
        cond += " AND po.creation <= '%s'" % to_dt
    po_dict = frappe.db.sql("""SELECT po.name as po_no, pod.name, po.creation, pod.qty, pod.idx,
        po.amended_from
        FROM `tabPurchase Order` po, `tabPurchase Order Item` pod WHERE pod.parent = po.name
        AND pod.item_code = '%s' AND pod.received_qty > 0 %s
        ORDER BY po.transaction_date DESC, pod.name LIMIT 100""" % (it_name, cond), as_dict=1)
    return po_dict


def get_avg_days_for_po(po_dict):
    avg_days_dict = frappe._dict({})
    avg_days, days_wt, tot_qty = 0, 0, 0
    query = """SELECT pr.name as pr, pri.name, pr.posting_date, pri.qty
        FROM `tabPurchase Receipt` pr, `tabPurchase Receipt Item` pri
        WHERE pr.name = pri.parent AND pri.purchase_order_item = '%s'
        ORDER BY pr.posting_date DESC""" % po_dict.name
    grn_dict = frappe.db.sql(query, as_dict=1)
    for pr in grn_dict:
        base_po = get_base_doc("Purchase Order", po_dict.po_no)
        pod = frappe.get_doc("Purchase Order", base_po)
        po_dict["creation"] = pod.creation
        days = (pr.posting_date - (po_dict.creation).date()).days
        if days > 0:
            tot_qty += pr.qty
            days_wt += days * pr.qty
    if tot_qty > 0:
        avg_days = auto_round_up(days_wt / tot_qty)
    else:
        avg_days = 0
    avg_days_dict["tot_qty"] = tot_qty
    avg_days_dict["avg_days"] = avg_days
    return avg_days_dict
