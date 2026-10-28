# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import copy
import frappe
from frappe.utils import cint, flt
from .item_attribute_utils import chunks
from .other_utils import get_weighted_average


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
    return get_detailed_po_lead_times([it_name], frm_dt, to_dt).get(it_name, [])


def get_detailed_po_lead_times(item_names, frm_dt=None, to_dt=None):
    """
    Returns {item: list of Purchase Order item dicts with their GRNs} for many items. The latest
    Purchase Orders (max transactions in RIGPL Settings) are used for each item.
    """
    max_trans = cint(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings",
        "max_transactions_for_lead_time_to_consider")) or 10
    po_tab = frappe.qb.DocType("Purchase Order")
    pod_tab = frappe.qb.DocType("Purchase Order Item")
    detailed = {}
    for chunk in chunks(item_names):
        query = (
            frappe.qb.from_(pod_tab)
            .join(po_tab)
            .on(pod_tab.parent == po_tab.name)
            .select(
                po_tab.name.as_("trans_name"),
                pod_tab.name.as_("trans_det_name"),
                po_tab.creation,
                po_tab.transaction_date,
                pod_tab.qty,
                pod_tab.idx,
                po_tab.amended_from,
                pod_tab.item_code,
            )
            .where(pod_tab.item_code.isin(chunk) & (pod_tab.received_qty > 0))
            .orderby(pod_tab.item_code)
            .orderby(po_tab.transaction_date, order=frappe.qb.desc)
            .orderby(pod_tab.name)
        )
        if frm_dt:
            query = query.where(po_tab.creation >= frm_dt)
        if to_dt:
            query = query.where(po_tab.creation <= to_dt)
        po_by_item = {}
        for row in query.run(as_dict=True):
            rows = po_by_item.setdefault(row.item_code, [])
            if len(rows) < max_trans:
                rows.append(row)
        po_rows = [row for rows in po_by_item.values() for row in rows]
        if not po_rows:
            continue
        base_creation = get_base_po_creation(po_rows)
        grn_by_pod = get_grn_for_po_items([row.trans_det_name for row in po_rows])

        for item_name, rows in po_by_item.items():
            po_dict = []
            trans_wt = len(rows)
            for row in rows:
                pod = frappe._dict({"trans_name": row.trans_name,
                    "trans_det_name": row.trans_det_name, "based_on": "Purchase Order",
                    "creation": row.creation, "transaction_date": row.transaction_date,
                    "qty": row.qty, "idx": row.idx, "amended_from": row.amended_from})
                pod["calc_trans_date"] = (base_creation.get(pod.trans_name) or pod.creation).date()
                pod["trans_wt"] = trans_wt
                trans_wt -= 1
                grn_dict = copy.deepcopy(grn_by_pod.get(pod.trans_det_name, []))
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
                po_dict.append(get_avg_days_for_po_dict(pod))
            detailed[item_name] = po_dict
    return detailed


def get_base_po_creation(po_rows):
    """
    Returns {Purchase Order: creation of its first version} for the amended Purchase Orders, like
    get_base_doc but one query for each level of amendments
    """
    po_tab = frappe.qb.DocType("Purchase Order")
    amended_from = {row.trans_name: row.amended_from for row in po_rows}
    to_read = {name for name in amended_from.values() if name and name not in amended_from}
    while to_read:
        rows = (
            frappe.qb.from_(po_tab)
            .select(po_tab.name, po_tab.amended_from)
            .where(po_tab.name.isin(list(to_read)))
            .run()
        )
        amended_from.update(dict(rows))
        # A missing Purchase Order ends the chain
        amended_from.update({name: None for name in to_read if name not in amended_from})
        to_read = {name for name in amended_from.values() if name and name not in amended_from}

    base_po = {}
    for row in po_rows:
        name = row.trans_name
        while amended_from.get(name):
            name = amended_from[name]
        if name != row.trans_name:
            base_po[row.trans_name] = name
    creation = {}
    if base_po:
        creation = dict(
            frappe.qb.from_(po_tab)
            .select(po_tab.name, po_tab.creation)
            .where(po_tab.name.isin(list(set(base_po.values()))))
            .run()
        )
    return {name: creation.get(base) for name, base in base_po.items()}


def get_grn_for_po_items(po_detail_names):
    """
    Returns {Purchase Order Item: GRN rows ordered by posting date descending}
    """
    pr_tab = frappe.qb.DocType("Purchase Receipt")
    pri_tab = frappe.qb.DocType("Purchase Receipt Item")
    grn_by_pod = {}
    for chunk in chunks(po_detail_names):
        rows = (
            frappe.qb.from_(pri_tab)
            .join(pr_tab)
            .on(pr_tab.name == pri_tab.parent)
            .select(
                pr_tab.name.as_("sub_trans_name"),
                pr_tab.creation.as_("sub_trans_creation"),
                pr_tab.posting_date.as_("sub_trans_date"),
                pri_tab.qty.as_("sub_trans_qty"),
                pri_tab.purchase_order_item,
            )
            .where(pri_tab.purchase_order_item.isin(chunk))
            .orderby(pr_tab.posting_date, order=frappe.qb.desc)
            .run(as_dict=True)
        )
        for row in rows:
            grn = frappe._dict({"sub_trans_name": row.sub_trans_name,
                "sub_trans_type": "Purchase Receipt", "sub_trans_creation": row.sub_trans_creation,
                "sub_trans_date": row.sub_trans_date, "sub_trans_qty": row.sub_trans_qty})
            grn_by_pod.setdefault(row.purchase_order_item, []).append(grn)
    return grn_by_pod


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
