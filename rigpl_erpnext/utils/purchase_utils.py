# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from .other_utils import auto_round_up, get_base_doc, get_weighted_average


def get_po_pend_qty(item_code, warehouse=None):
    """
    Returns integer value as per pending PO for an Item Code
    """
    wh_cond = ""
    if warehouse:
        wh_cond += f" AND pod.warehouse = '{warehouse}'"
    po_query = f"""SELECT po.name as po_no, pod.name as pod_name,
    (pod.qty - pod.received_qty) as poq, pod.idx, pod.item_code
    FROM `tabPurchase Order` po, `tabPurchase Order Item` pod
    WHERE po.docstatus = 1 AND po.status != 'Closed' AND pod.received_qty < pod.qty
    AND pod.parent = po.name AND pod.item_code = '{item_code}' {wh_cond}"""
    po_dict = frappe.db.sql(po_query, as_dict=1)
    poq = 0
    if po_dict:
        for pono in po_dict:
            poq += pono.poq
    return poq


def get_purchase_lead_times(item_name, frm_dt=None, to_dt=None):
    """
    Returns a dict with item_name and lead_times based on Purchase Orders to GRN times
    Lead Time Dict would have following keys: item_name, avg_days, no_of_trans, total_qty
    min_days, max_days, avg_days_wt, tot_qty
    avg_days_wt is the weighted average delivery time
    """
    ldt_dict = frappe._dict({})
    ldt_dict["item_name"] = item_name
    po_dict = get_po_data_for_item(item_name, frm_dt=frm_dt, to_dt=to_dt)
    ldt_dict["no_of_trans"] = len(po_dict)
    for pod in po_dict:
        if ldt_dict.get("min_days", 0) == 0:
            ldt_dict["min_days"] = pod.avg_days
        else:
            if ldt_dict["min_days"] > pod.min_days:
                ldt_dict["min_days"] = pod.min_days
        if ldt_dict.get("max_days", 0) == 0:
            ldt_dict["max_days"] = pod.max_days
        else:
            if ldt_dict["max_days"] < pod.max_days:
                ldt_dict["max_days"] = pod.max_days
    avg_days_wt, tot_qty, wt_key2 = get_weighted_average(list_of_data=po_dict, avg_key="avg_days",
        wt_key="completed_qty", wt_key2="trans_wt")
    ldt_dict["avg_days_wt"] = auto_round_up(avg_days_wt)
    ldt_dict["total_qty"] = int(tot_qty)
    return ldt_dict


def get_po_data_for_item(it_name, frm_dt=None, to_dt=None):
    """
    Returns the PO dictionary for an Item in a period also limits the no of transactions to
    defined in settings adds the min_days, max_days, avg_days and trans_wt keys to dictionary.
    """
    max_trans = frappe.get_value("RIGPL Settings", "RIGPL Settings",
        "max_transactions_for_lead_time_to_consider")
    if max_trans == 0:
        max_trans = 10
    cond = ""
    if frm_dt:
        cond += f" AND po.creation >= '{frm_dt}'"
    if to_dt:
        cond += f" AND po.creation <= '{to_dt}'"
    po_query = f"""SELECT po.name as trans_name, pod.name as pod_name,
        po.creation, pod.qty, pod.idx, po.amended_from
        FROM `tabPurchase Order` po, `tabPurchase Order Item` pod
        WHERE pod.parent = po.name AND pod.item_code = '{it_name}' AND pod.received_qty > 0 {cond}
        ORDER BY po.transaction_date DESC, pod.name LIMIT {max_trans}"""
    po_dict = frappe.db.sql(po_query, as_dict=1)
    trans_wt = len(po_dict)
    for pod in po_dict:
        pod = get_avg_days_for_po(pod)
        pod["trans_wt"] = trans_wt
        pod["trans_date"] = (pod.creation).date()
        trans_wt -= 1
    return po_dict


def get_avg_days_for_po(po_dict):
    avg_days_dict = frappe._dict({})
    base_po = get_base_doc("Purchase Order", po_dict.trans_name)
    pod = frappe.get_doc("Purchase Order", base_po)
    po_dict["creation"] = pod.creation
    avg_days, days_wt, tot_qty = 0, 0, 0
    query = f"""SELECT pr.name as pr, pri.name as det_name, pr.posting_date, pri.qty
        FROM `tabPurchase Receipt` pr, `tabPurchase Receipt Item` pri
        WHERE pr.name = pri.parent AND pri.purchase_order_item = '{po_dict.pod_name}'
        ORDER BY pr.posting_date DESC"""
    grn_dict = frappe.db.sql(query, as_dict=1)
    for grn in grn_dict:
        days = max((grn.posting_date - (po_dict.creation).date()).days, 1)
        if not po_dict.get("min_days", None) or po_dict.get("min_days", 0) > days or \
                po_dict.get("min_days", 0) == 0:
            po_dict["min_days"] = days
        if not po_dict.get("max_days", None) or po_dict.get("max_days", 0) < days:
            po_dict["max_days"] = days
        tot_qty += grn.qty
        days_wt += days * grn.qty
    if tot_qty > 0:
        avg_days = int(days_wt / tot_qty)
    else:
        avg_days = 0
    po_dict["completed_qty"] = tot_qty
    po_dict["avg_days"] = avg_days
    return po_dict
