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


def get_detailed_po_lead_time_for_item(it_name, frm_dt=None, to_dt=None):
    """
    Returns the dict of Purchase Orders for Item in a date range with
    Actual dates along with the GRNs
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
    po_query = f"""SELECT po.name as trans_name, pod.name as trans_det_name,
        'Purchase Order' as based_on, po.creation, po.transaction_date, pod.qty, pod.idx,
        po.amended_from
        FROM `tabPurchase Order` po, `tabPurchase Order Item` pod
        WHERE pod.parent = po.name AND pod.item_code = '{it_name}' AND pod.received_qty > 0 {cond}
        ORDER BY po.transaction_date DESC, pod.name LIMIT {max_trans}"""
    po_dict = frappe.db.sql(po_query, as_dict=1)
    trans_wt = len(po_dict)
    for pod in po_dict:
        base_po = get_base_doc("Purchase Order", pod.trans_name)
        if base_po != pod.trans_name:
            pod["calc_trans_date"] = frappe.get_value("Purchase Order", base_po, "creation").date()
        else:
            pod["calc_trans_date"] = (pod.creation).date()
        pod["trans_wt"] = trans_wt
        trans_wt -= 1
        grn_dict = get_grn_for_po(pod.trans_det_name)
        if grn_dict:
            sub_trans_wt = len(grn_dict)
            for grn in grn_dict:
                grn["sub_trans_wt"] = sub_trans_wt
                sub_trans_wt -= 1
                creat_diff = ((grn.sub_trans_creation).date() - pod.calc_trans_date).days
                trans_diff = (grn.sub_trans_date - pod.calc_trans_date).days
                actual_diff = max(creat_diff, trans_diff, 1)
                grn["days_diff"] = actual_diff
            pod["sub_trans"] = grn_dict
        pod = get_avg_days_for_po_dict(pod)
    return po_dict


def get_avg_days_for_po_dict(po_dict):
    """
    Updates a dictionary with average days data for a particular PO based on GRNs
    """
    po_dict.update({"no_of_sub_trans": 0, "trans_max_days": 0, "trans_min_days": 0,
        "trans_avg_days": 0, "trans_qty": 0})
    if po_dict.get("sub_trans", None):
        avg_days_wt, tot_qty, wt_key2 = get_weighted_average(list_of_data=po_dict.sub_trans,
            avg_key="days_diff", wt_key="sub_trans_qty", wt_key2="sub_trans_wt")
        po_dict["no_of_sub_trans"] = len(po_dict.sub_trans)
        po_dict["trans_avg_days"] = avg_days_wt
        po_dict["trans_qty"] = tot_qty
        for sub in po_dict.sub_trans:
            if po_dict["trans_max_days"] < sub.days_diff:
                po_dict["trans_max_days"] = sub.days_diff
            if po_dict["trans_min_days"] > 0:
                if po_dict["trans_min_days"] > sub.days_diff:
                    po_dict["trans_min_days"] = sub.days_diff
            else:
                po_dict["trans_min_days"] = sub.days_diff
    return po_dict


def get_grn_for_po(po_detail_name):
    """
    Returns a dictonary for po detail name since there can be multiple GRN for a PO
    """
    grn_dict = frappe.db.sql(f"""SELECT pr.name as sub_trans_name,
        'Purchase Receipt' as sub_trans_type,
        pr.creation as sub_trans_creation, pr.posting_date as sub_trans_date,
        pri.qty as sub_trans_qty
        FROM `tabPurchase Receipt` pr, `tabPurchase Receipt Item` pri
        WHERE pr.name = pri.parent AND pri.purchase_order_item = '{po_detail_name}'
        ORDER BY pr.posting_date DESC""", as_dict=1)
    return grn_dict
