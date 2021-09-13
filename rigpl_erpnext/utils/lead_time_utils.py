# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import sys
import frappe
from frappe.utils import flt
from .stock_utils import get_quantities_for_item
from .process_sheet_utils import get_last_operation_for_psheet
from .purchase_utils import get_purchase_lead_times
from .other_utils import auto_round_up, get_base_doc, get_weighted_average


def get_item_lead_time(item_name, frm_dt=None, to_dt=None):
    """
    This function gets the lead time for an item based on Purchase or Manufacture
    """
    ldt_dict = frappe._dict({})
    itd = frappe.get_doc("Item", item_name)
    if itd.include_item_in_manufacturing == 1:
        # Items which are used for Manufacturing would be taken from Process Sheet
        ldt_dict = get_manuf_lead_time(item_name, frm_dt=frm_dt, to_dt=to_dt)
        ldt_dict["based_on"] = "Process Sheet"
    elif itd.is_purchase_item == 1:
        # Check the days between the PO and GRN if ZERO days then dont consider that
        # set for calculations
        ldt_dict = get_purchase_lead_times(item_name, frm_dt=frm_dt, to_dt=to_dt)
        ldt_dict["based_on"] = "Purchase Order"
    else:
        # Check which items are there and device a formula for that as well.
        ldt_dict["avg_days_wt"] = 0
        ldt_dict["based_on"] = "Unknown"
        print(f"Item {item_name} is neither Sales nor Purchase so Lead Time is Set to 0")
    return ldt_dict


def get_manuf_lead_time(item_name, frm_dt=None, to_dt=None):
    """
    Returns a dict with item_name and lead_times based on Production Orders or Work Orders
    Lead Time Dict would have following keys: item_name, avg_days, no_of_trans, total_qty
    min_days, max_days, avg_days_wt, tot_qty
    avg_days_wt is the weighted average delivery time
    """
    tot_qty = 0
    days_data = get_manuf_days_data_for_item(item_name, frm_dt=frm_dt, to_dt=to_dt)
    ldt_dict = frappe._dict({})
    ldt_dict.update({"item_name": item_name, "no_of_trans": len(days_data), "min_days": 0,
        "max_days": 0, "total_qty": 0, "avg_days_wt": 0})
    for psh in days_data:
        if ldt_dict.get("min_days", 0) == 0 or ldt_dict.get("min_days", 0) > psh.min_days:
            ldt_dict["min_days"] = psh.min_days
        if ldt_dict.get("max_days", 0) == 0 or ldt_dict.get("max_days", 0) < psh.max_days:
            ldt_dict["max_days"] = psh.max_days
        tot_qty += psh.completed_qty
    ldt_dict["total_qty"] = tot_qty
    avg_days_wt, total_qty, wt_key2 = get_weighted_average(days_data, avg_key= "avg_days",
        wt_key="avg_days", wt_key2="trans_wt")
    ldt_dict["avg_days_wt"] = avg_days_wt
    ldt_dict["total_qty"] = total_qty
    return ldt_dict


def get_manuf_days_data_for_item(it_name, frm_dt=None, to_dt=None):
    """
    Returns a dictionary of Process Sheets for an Item
    """
    max_trans = frappe.get_value("RIGPL Settings", "RIGPL Settings",
        "max_transactions_for_lead_time_to_consider")
    if max_trans == 0:
        max_trans = 10
    cond = ""
    if frm_dt:
        cond += f" AND ps.date >= '{frm_dt}'"
    if to_dt:
        cond += f" AND ps.date <= '{to_dt}'"
    psd_list = []
    ps_dict = frappe.db.sql(f"""SELECT ps.name, ps.date, ps.quantity, ps.produced_qty,
        ps.production_item, ps.status
        FROM `tabProcess Sheet` ps WHERE ps.docstatus = 1 AND ps.production_item = '{it_name}'
        AND ps.produced_qty > 0
        ORDER BY ps.date DESC LIMIT {max_trans}""", as_dict=1)
    if ps_dict:
        max_wt = len(ps_dict)
        for psh in ps_dict:
            days_data = get_process_sheet_days(psh.name)
            days_data["trans_name"] = psh.name
            days_data["trans_wt"] = max_wt
            max_wt -= 1
            if days_data.completed_qty > 0:
                psd_list.append(days_data)
    return psd_list


def get_process_sheet_days(ps_name, op_name=None, dont_consider=1):
    """
    Returns a dictionary for avg days for processing process sheet
    Dict Keys ps_name, completed_qty, min_days, max_days, avg_days
    """
    ps_days = frappe._dict()
    ps_days.update({"ps_name": ps_name, "completed_qty":0, "min_days":0, "max_days":0,
        "avg_days":0})
    psd = frappe.get_doc("Process Sheet", ps_name)
    if psd.docstatus != 1:
        print(f"{ps_name} with Docstatus = {psd.docstatus} has No Working")
        return ps_days
    else:
        if psd.produced_qty > 0:
            # Update the psdoc date with the date when first JCR is submitted to signify start of
            # operations for a Process Sheet
            psd = update_process_sheet_start_date(psd)
            if not op_name:
                op_name = get_last_operation_for_psheet(psd, dont_consider)
            for oper in psd.operations:
                if oper.operation == op_name:
                    ps_days = get_full_processing_for_psheet(psd, op_name=oper.operation,
                        ps_days=ps_days)
                    ps_days["trans_date"] = psd.date
            return ps_days
        else:
            print(f"{ps_name} Still Waiting for 1st Process to Complete")
            return ps_days


def update_process_sheet_start_date(psdoc):
    """
    This function updates the start date for a Process Sheet basically if there is a lag between
    submission of Prodcess Sheet and completion of first process then it should update the PS date
    to the date of first operation completion. For Ex: Is PS is submitted on 1st Jan but the first
    operation is completed on 20th Feb so item was in planning for 50 days which should not be
    included in calculation of lead time.
    """

    for opr in psdoc.operations:
        if opr.idx == 1:
            first_op_name = opr.operation
    first_jcr = frappe.db.sql(f"""SELECT name, posting_date, total_completed_qty
        FROM `tabProcess Job Card RIGPL`
        WHERE docstatus = 1 AND process_sheet = '{psdoc.name}' AND total_completed_qty > 0
        AND operation = '{first_op_name}'
        ORDER BY posting_date, posting_time LIMIT 1""", as_dict=1)
    if first_jcr:
        if first_jcr[0].posting_date != psdoc.date:
            psdoc.date = first_jcr[0].posting_date
    return psdoc


def get_full_processing_for_psheet(psdoc, op_name, ps_days):
    """
    For Given Process Sheet Doc, Operation and PS Days dict this function returns the updated
    ps_days dict with the values of Min, Max and Qty and Avg Days for Process Sheet Operation
    Basically its telling how many days it took to complete that process sheet operation
    """
    # Get all PSheets before the Existing PSheet for FIFO
    ps_fifo_queue = get_fifo_ps_qty(psdoc, op_name)
    ps_days = get_completion_time_for_ps(psdoc, op_name, ps_days, ps_fifo_queue)
    return ps_days


def get_completion_time_for_ps(psdoc, op_name, ps_days, fifo_qty):
    """
    Returns days_data dict with min_days, max_days, completed_qty, avg_days keys
    """
    qty_remaining = psdoc.produced_qty
    jcr_list = get_jcr_after_ps(psdoc, op_name)
    if jcr_list:
        if fifo_qty > 0:
            jcr_list_wo_fifo = update_jcr_as_per_fifo(jcr_list, fifo_qty)
        else:
            jcr_list_wo_fifo = jcr_list
    else:
        jcr_list_wo_fifo = []
    if jcr_list_wo_fifo:
        for jcr in jcr_list_wo_fifo:
            if qty_remaining > 0:
                days_taken = (jcr.posting_date - psdoc.date).days + 1
                if days_taken < 1:
                    print(f"For {jcr} Days Taken is Coming Less than 1")
                    sys.exit()
                old_wt_avg = ps_days.avg_days * ps_days.completed_qty
                if days_taken > ps_days.max_days:
                    ps_days.max_days = days_taken
                if ps_days.min_days == 0 or ps_days.min_days > days_taken:
                    ps_days.min_days = days_taken
                if qty_remaining > jcr.total_completed_qty:
                    new_wt_avg = jcr.total_completed_qty * days_taken
                    ps_days.avg_days = int((old_wt_avg + new_wt_avg) / (jcr.total_completed_qty +
                                            ps_days.completed_qty))
                    ps_days.completed_qty += jcr.total_completed_qty
                    qty_remaining = qty_remaining - jcr.total_completed_qty
                else:
                    new_wt_avg = qty_remaining * days_taken
                    ps_days.avg_days = int((old_wt_avg + new_wt_avg) / (qty_remaining +
                                            ps_days.completed_qty))
                    ps_days.completed_qty += qty_remaining
                    qty_remaining = 0
            else:
                break
    return ps_days


def update_jcr_as_per_fifo(jcr_list, fifo_qty):
    """
    Removes the Job Cards as per Fifo so if Fifo Qty = 100 and completed qty in first 2 JCR is 110
    then the function removes first one and amends the completed qty for 2nd by making it 10
    """
    bal_fifo = fifo_qty
    for jcr in jcr_list:
        if bal_fifo > 0:
            if jcr.total_completed_qty > bal_fifo:
                jcr["total_completed_qty"] = jcr["total_completed_qty"] - bal_fifo
            else:
                bal_fifo = bal_fifo - jcr.total_completed_qty
                jcr_list = list(filter(lambda i:i["name"] != jcr.name, jcr_list))
        else:
            break
    return jcr_list


def get_fifo_ps_qty(psdoc, op_name):
    """
    Returns the Quantity pending before the Process Sheet following FIFO
    """
    jcr_completed = get_comp_jcr_before_psheet(psdoc, op_name)
    before_ps_comp_qty = get_comp_qty_before_ps(psdoc)
    fifo_queue = max(before_ps_comp_qty - jcr_completed, 0)
    return fifo_queue


def get_comp_qty_before_ps(psdoc):
    """
    Returns Integer Quantity for Produced Qty before the PSheet
    """
    psq = frappe.db.sql(f"""SELECT name, date, SUM(produced_qty) as tot_qty FROM `tabProcess Sheet`
        WHERE docstatus = 1 AND production_item = '{psdoc.production_item}'
        AND date < '{psdoc.date}' AND name != '{psdoc.name}' AND produced_qty > 0
        ORDER BY date DESC""", as_dict=1)
    psq = flt(psq[0].tot_qty)
    return psq


def get_jcr_after_ps(psdoc, op_name):
    """
    Returns dictionary of JCR after the Process Sheet for Particular operaion
    """
    jcdict = frappe.db.sql(f"""SELECT name, operation, docstatus, status, total_completed_qty,
        posting_date, posting_time
        FROM `tabProcess Job Card RIGPL` WHERE docstatus = 1 AND posting_date >= '{psdoc.date}'
        AND production_item = '{psdoc.production_item}' AND operation = '{op_name}'
        AND total_completed_qty > 0
        ORDER BY posting_date ASC, posting_time ASC""", as_dict=1)
    return jcdict


def get_comp_jcr_before_psheet(psdoc, op_name):
    """
    Retuns integer quantity for Operation in Process Sheet after the date of PS
    """
    jc_qty = 0
    jc_list = frappe.db.sql(f"""SELECT name, operation, docstatus, status, total_completed_qty,
            posting_date, total_qty, for_quantity
            FROM `tabProcess Job Card RIGPL` WHERE operation = '{op_name}' AND docstatus != 2
            AND posting_date < '{psdoc.date}' AND production_item = '{psdoc.production_item}'
            ORDER BY posting_date DESC""", as_dict=1)
    for jcr in jc_list:
        jc_qty += jcr.total_completed_qty
    return jc_qty
