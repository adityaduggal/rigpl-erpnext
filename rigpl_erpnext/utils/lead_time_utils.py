# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import sys

import frappe
from frappe.utils import flt

from ..manufacturing_rigpl.utils.process_sheet_utils import (
    get_last_operation_for_psheet,
)
from .other_utils import auto_round_up, get_base_doc, get_weighted_average
from .purchase_utils import get_avg_days_for_po_dict, get_detailed_po_lead_time_for_item
from .stock_utils import get_quantities_for_item


def get_item_lead_time(item_name="HR1XRE007Z4", frm_dt=None, to_dt=None):
    """
    This function gets the lead time for an item based on Purchase or Manufacture
    """
    ldt_dict = frappe._dict({})
    itd = frappe.get_doc("Item", item_name)
    if itd.include_item_in_manufacturing == 1:
        # Items which are used for Manufacturing would be taken from Process Sheet
        ldt_dict = get_manuf_lead_time(item_name, frm_dt=frm_dt, to_dt=to_dt)
    elif itd.is_purchase_item == 1:
        # Check the days between the PO and GRN if ZERO days then dont consider that
        # set for calculations
        ldt_dict = get_purchase_lead_times(item_name, frm_dt=frm_dt, to_dt=to_dt)
    else:
        # Check which items are there and device a formula for that as well.
        ldt_dict["avg_days_wt"] = 0
        ldt_dict["based_on"] = "Unknown"
        print(
            f"Item {item_name} is neither Sales nor Purchase so Lead Time is Set to 0"
        )
    return ldt_dict


def get_manuf_lead_time(item_name, frm_dt=None, to_dt=None):
    """
    Returns a dict with item_name and lead_times based on Production Orders or Work Orders
    Lead Time Dict would have following keys: item_name, avg_days, no_of_trans, total_qty
    min_days, max_days, avg_days_wt, tot_qty
    avg_days_wt is the weighted average delivery time
    """
    ldt_dict = frappe._dict({})
    manf_dict = get_detailed_manuf_lead_time_for_item(item_name, frm_dt, to_dt)
    # frappe.throw(str(manf_dict))
    ldt_dict["item_name"] = item_name
    ldt_dict["no_of_trans"] = len(manf_dict)
    avg_days_wt, tot_qty, wt_key2 = get_weighted_average(
        list_of_data=manf_dict,
        avg_key="trans_avg_days",
        wt_key="trans_qty",
        wt_key2="trans_wt",
    )
    ldt_dict["based_on"] = "Process Sheet"
    ldt_dict["avg_days_wt"] = avg_days_wt
    ldt_dict["total_qty"] = tot_qty
    for psn in manf_dict:
        if psn.trans_min_days < ldt_dict.get("min_days", 9999):
            ldt_dict["min_days"] = psn.trans_min_days
        if psn.trans_max_days > ldt_dict.get("max_days", 0):
            ldt_dict["max_days"] = psn.trans_max_days
    return ldt_dict


def get_purchase_lead_times(item_name="RHP40XSQ00MG0", frm_dt=None, to_dt=None):
    """
    Returns a dictionary for an item in date range
    Dictionary consists of PO Data and corresponding GRN and times
    """
    ldt_dict = frappe._dict({})
    po_dict = get_detailed_po_lead_time_for_item(item_name, frm_dt, to_dt)
    ldt_dict["item_name"] = item_name
    ldt_dict["no_of_trans"] = len(po_dict)
    avg_days_wt, tot_qty, wt_key2 = get_weighted_average(
        list_of_data=po_dict,
        avg_key="trans_avg_days",
        wt_key="trans_qty",
        wt_key2="trans_wt",
    )
    ldt_dict["based_on"] = "Purchase Order"
    ldt_dict["avg_days_wt"] = avg_days_wt
    ldt_dict["total_qty"] = tot_qty
    for pod in po_dict:
        if pod.trans_min_days < ldt_dict.get("min_days", 9999):
            ldt_dict["min_days"] = pod.trans_min_days
        if pod.trans_max_days > ldt_dict.get("max_days", 0):
            ldt_dict["max_days"] = pod.trans_max_days
    return ldt_dict


def get_detailed_manuf_lead_time_for_item(item_name, frm_dt=None, to_dt=None):
    """
    Returns a dictionary for an item in date range with details of Process Sheets and JCR
    """
    max_trans = frappe.get_value(
        "RIGPL Settings", "RIGPL Settings", "max_transactions_for_lead_time_to_consider"
    )
    if max_trans == 0:
        max_trans = 10
    cond = ""
    if frm_dt:
        cond += f" AND ps.date >= '{frm_dt}'"
    if to_dt:
        cond += f" AND ps.date <= '{to_dt}'"
    ps_query = f"""SELECT ps.name as trans_name, 'Process Sheet' as based_on, ps.creation, ps.date,
    ps.quantity, ps.produced_qty, ps.amended_from
    FROM `tabProcess Sheet` ps
    WHERE ps.docstatus = 1 AND ps.production_item = '{item_name}' AND ps.produced_qty > 0 {cond}
    ORDER BY ps.date DESC, ps.name DESC LIMIT {max_trans}"""
    ps_dict = frappe.db.sql(ps_query, as_dict=1)
    trans_wt = len(ps_dict)
    for psn in ps_dict:
        psn["calc_trans_date"] = get_start_date_for_psheet(psn.trans_name)
        psn["trans_wt"] = trans_wt
        trans_wt -= 1
        jcr_dict = get_jcr_for_ps(psn.trans_name)
        if jcr_dict:
            sub_trans_wt = 1
            for jcr in jcr_dict:
                jcr["sub_trans_wt"] = sub_trans_wt
                sub_trans_wt += 1
                jcr["days_diff"] = max(
                    (jcr.sub_trans_date - psn.calc_trans_date).days + 1, 1
                )
        psn["sub_trans"] = jcr_dict
        psn = get_avg_days_for_po_dict(psn)
    return ps_dict


def get_jcr_for_ps(ps_name):
    """
    Returns a dictionary for the JCR used for a Process Sheet based on FIFO
    """
    sub_trans = []
    psd = frappe.get_doc("Process Sheet", ps_name)
    last_op = get_last_operation_for_psheet(psd, no_cons_ld_time=1)
    tps = flt(
        frappe.db.sql(
            f"""SELECT SUM(produced_qty) as tps FROM `tabProcess Sheet`
        WHERE docstatus=1 AND production_item = '{psd.production_item}'""",
            as_list=1,
        )[0][0]
    )
    qty_compl_before_ps = get_total_completed_before_ps(psd)
    ps_comp = frappe.get_value("Process Sheet", ps_name, "produced_qty")
    jct = frappe.db.sql(
        f"""SELECT SUM(total_completed_qty) as total_jc
        FROM `tabProcess Job Card RIGPL` WHERE docstatus=1
        AND production_item = '{psd.production_item}' AND operation = '{last_op}'""",
        as_list=1,
    )
    jc_total = flt(jct[0][0])
    if jc_total > tps:
        excess_qty = jc_total - tps
    else:
        excess_qty = 0
    jc_query = f"""SELECT name as sub_trans_name, posting_date as sub_trans_date,
    'Process Job Card RIGPL' as sub_trans_type, total_completed_qty as sub_trans_qty,
    production_item, operation
    FROM `tabProcess Job Card RIGPL` WHERE docstatus = 1
    AND production_item = '{psd.production_item}' AND operation = '{last_op}'
    ORDER BY posting_date ASC, posting_time ASC"""
    jcr_list = frappe.db.sql(jc_query, as_dict=1)
    ps_qty_left = ps_comp
    # If Excess Qty of JCR is produced than Process Sheet then remove the same first
    if excess_qty > 0:
        for jcr in jcr_list:
            if excess_qty >= jcr.sub_trans_qty:
                excess_qty -= jcr.sub_trans_qty
                jcr.sub_trans_qty = 0
                jcr_list.remove(jcr)
            else:
                jcr.sub_trans_qty -= excess_qty
                excess_qty = 0
    for jcr in jcr_list:
        if qty_compl_before_ps > 0:
            if qty_compl_before_ps >= jcr.sub_trans_qty:
                qty_compl_before_ps -= jcr.sub_trans_qty
            else:
                jcr.sub_trans_qty -= qty_compl_before_ps
                qty_compl_before_ps = 0
                ps_qty_left -= jcr.sub_trans_qty
                sub_trans.append(jcr.copy())
        else:
            if ps_qty_left > 0:
                if ps_qty_left >= jcr.sub_trans_qty:
                    sub_trans.append(jcr.copy())
                    ps_qty_left -= jcr.sub_trans_qty
                else:
                    jcr.sub_trans_qty = ps_qty_left
                    ps_qty_left = 0
                    sub_trans.append(jcr.copy())
            else:
                break
    return sub_trans


def get_total_completed_before_ps(psdoc):
    """
    Returns the quantity completed before a Process Sheet which is completed for Last Operation
    """
    ps_comp = frappe.db.sql(
        f"""SELECT SUM(produced_qty) as ps_qty
        FROM `tabProcess Sheet` WHERE docstatus = 1 AND produced_qty > 0
        AND production_item = '{psdoc.production_item}' AND date <= '{psdoc.date}'
        AND name != '{psdoc.name}'""",
        as_list=1,
    )
    qty_comp = flt(ps_comp[0][0])
    return qty_comp


def get_start_date_for_psheet(ps_name):
    """
    This function returns the start date for a Process Sheet Name basically if there is a lag
    between submission of Prodcess Sheet and completion of first process then it should send
    the start date as the date of first operation completion. For Ex: Is PS is submitted on 1st Jan
    but the first operation is completed on 20th Feb so item was in planning for around 50 days
    which should not be included in calculation of lead time.
    But if there is only 1 Process to be considered for the Production then it would take start
    date as the date of creation of the Process Sheet
    """
    psd = frappe.get_doc("Process Sheet", ps_name)
    last_op = get_last_operation_for_psheet(psd, no_cons_ld_time=1)
    for opr in psd.operations:
        if opr.idx == 1:
            first_op_name = opr.operation
    if first_op_name != last_op:
        first_jcr = frappe.db.sql(
            f"""SELECT name, posting_date, total_completed_qty
            FROM `tabProcess Job Card RIGPL`
            WHERE docstatus = 1 AND process_sheet = '{psd.name}' AND total_completed_qty > 0
            AND operation = '{first_op_name}'
            ORDER BY posting_date, posting_time LIMIT 1""",
            as_dict=1,
        )
        if first_jcr:
            if first_jcr[0].posting_date > psd.date:
                start_date = first_jcr[0].posting_date
            else:
                start_date = psd.date
        else:
            start_date = ""
    else:
        start_date = (psd.creation).date()
    return start_date
