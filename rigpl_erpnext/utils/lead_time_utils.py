# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import copy
import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt
from .item_attribute_utils import chunks
from ..manufacturing_rigpl.utils.process_sheet_utils import pick_last_operation
from .purchase_utils import get_detailed_po_lead_times, get_avg_days_for_po_dict
from .other_utils import get_weighted_average


def get_item_lead_time(item_name='HR1XRE007Z4', frm_dt=None, to_dt=None):
    """
    This function gets the lead time for an item based on Purchase or Manufacture
    """
    return get_items_lead_time([item_name], frm_dt=frm_dt, to_dt=to_dt)[item_name]


def get_items_lead_time(item_names, frm_dt=None, to_dt=None):
    """
    Returns {item name: lead time dict} based on Purchase or Manufacture for many items, with
    a fixed number of queries for each chunk of items
    """
    it_tab = frappe.qb.DocType("Item")
    lead_times = {}
    for chunk in chunks(item_names):
        item_flags = (
            frappe.qb.from_(it_tab)
            .select(it_tab.name, it_tab.include_item_in_manufacturing, it_tab.is_purchase_item)
            .where(it_tab.name.isin(chunk))
            .run(as_dict=True)
        )
        manuf_items = [itm.name for itm in item_flags if itm.include_item_in_manufacturing == 1]
        purchase_items = [itm.name for itm in item_flags
            if itm.include_item_in_manufacturing != 1 and itm.is_purchase_item == 1]
        manf_dict = get_detailed_manuf_lead_times(manuf_items, frm_dt, to_dt)
        po_dict = get_detailed_po_lead_times(purchase_items, frm_dt, to_dt)
        for itm in item_flags:
            if itm.include_item_in_manufacturing == 1:
                # Items which are used for Manufacturing would be taken from Process Sheet
                lead_times[itm.name] = get_lead_time_summary(itm.name,
                    manf_dict.get(itm.name, []), "Process Sheet")
            elif itm.is_purchase_item == 1:
                # Check the days between the PO and GRN if ZERO days then dont consider that
                # set for calculations
                lead_times[itm.name] = get_lead_time_summary(itm.name,
                    po_dict.get(itm.name, []), "Purchase Order")
            else:
                # Check which items are there and device a formula for that as well.
                lead_times[itm.name] = frappe._dict({"avg_days_wt": 0, "based_on": "Unknown"})
                print(f"Item {itm.name} is neither Sales nor Purchase so Lead Time is Set to 0")
    return lead_times


def get_manuf_lead_time(item_name, frm_dt=None, to_dt=None):
    """
    Returns a dict with item_name and lead_times based on Production Orders or Work Orders
    Lead Time Dict would have following keys: item_name, avg_days, no_of_trans, total_qty
    min_days, max_days, avg_days_wt, tot_qty
    avg_days_wt is the weighted average delivery time
    """
    manf_dict = get_detailed_manuf_lead_time_for_item(item_name, frm_dt, to_dt)
    return get_lead_time_summary(item_name, manf_dict, "Process Sheet")


def get_purchase_lead_times(item_name='RHP40XSQ00MG0', frm_dt=None, to_dt=None):
    """
    Returns a dictionary for an item in date range
    Dictionary consists of PO Data and corresponding GRN and times
    """
    po_dict = get_detailed_po_lead_times([item_name], frm_dt, to_dt).get(item_name, [])
    return get_lead_time_summary(item_name, po_dict, "Purchase Order")


def get_lead_time_summary(item_name, trans_list, based_on):
    """
    Returns the lead time dict for the transactions of an item: no_of_trans, the weighted
    average days (avg_days_wt), total_qty, min_days and max_days
    """
    ldt_dict = frappe._dict({})
    ldt_dict["item_name"] = item_name
    ldt_dict["no_of_trans"] = len(trans_list)
    avg_days_wt, tot_qty, wt_key2 = get_weighted_average(list_of_data=trans_list,
        avg_key="trans_avg_days", wt_key="trans_qty", wt_key2="trans_wt")
    ldt_dict["based_on"] = based_on
    ldt_dict["avg_days_wt"] = avg_days_wt
    ldt_dict["total_qty"] = tot_qty
    for trn in trans_list:
        if trn.trans_min_days < ldt_dict.get("min_days", 9999):
            ldt_dict["min_days"] = trn.trans_min_days
        if trn.trans_max_days > ldt_dict.get("max_days", 0):
            ldt_dict["max_days"] = trn.trans_max_days
    return ldt_dict


def get_detailed_manuf_lead_time_for_item(item_name, frm_dt=None, to_dt=None):
    """
    Returns a dictionary for an item in date range with details of Process Sheets and JCR
    """
    return get_detailed_manuf_lead_times([item_name], frm_dt, to_dt).get(item_name, [])


def get_detailed_manuf_lead_times(item_names, frm_dt=None, to_dt=None):
    """
    Returns {item: list of Process Sheet dicts with their JCR} for many items. The latest
    Process Sheets (max transactions in RIGPL Settings) are used for each item.
    """
    max_trans = cint(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings",
        "max_transactions_for_lead_time_to_consider")) or 10
    detailed = {}
    for chunk in chunks(item_names):
        ps_by_item = get_process_sheets(chunk)
        selected = {}
        for item_name, ps_list in ps_by_item.items():
            rows = [psn for psn in ps_list if psn.produced_qty > 0
                and (not frm_dt or str(psn.date) >= str(frm_dt))
                and (not to_dt or str(psn.date) <= str(to_dt))]
            selected[item_name] = rows[:max_trans]
        ps_names = [psn.name for rows in selected.values() for psn in rows]
        if not ps_names:
            continue
        operations = get_ps_operations(ps_names)
        op_flags, bt_flags = get_lead_time_operation_flags(
            {psn.bom_template for rows in selected.values() for psn in rows})
        first_jcr = get_first_jcr_for_ps(ps_names)
        jcr_by_item = get_jcr_for_items(list(selected))

        for item_name, rows in selected.items():
            tps = sum(flt(psn.produced_qty) for psn in ps_by_item[item_name])
            ps_dict = []
            trans_wt = len(rows)
            for psd in rows:
                op_names = operations.get(psd.name, [])
                last_op = pick_last_operation(op_names, op_flags,
                    bt_flags.get(psd.bom_template, {}), no_cons_ld_time=1)
                psn = frappe._dict({"trans_name": psd.name, "based_on": "Process Sheet",
                    "creation": psd.creation, "date": psd.date, "quantity": psd.quantity,
                    "produced_qty": psd.produced_qty, "amended_from": psd.amended_from})
                psn["calc_trans_date"] = get_start_date_for_psheet(psd, op_names, last_op,
                    first_jcr.get(psd.name, []))
                psn["trans_wt"] = trans_wt
                trans_wt -= 1
                jcr_list = [jcr for jcr in jcr_by_item.get(item_name, [])
                    if jcr.operation == last_op]
                jcr_dict = get_jcr_for_ps(psd, ps_by_item[item_name], jcr_list, tps)
                if jcr_dict and not psn.calc_trans_date:
                    # No completed first operation so the start date is not known
                    print(f"Process Sheet {psd.name} has no Start Date so it is not considered")
                    jcr_dict = []
                if jcr_dict:
                    sub_trans_wt = 1
                    for jcr in jcr_dict:
                        jcr["sub_trans_wt"] = sub_trans_wt
                        sub_trans_wt += 1
                        jcr["days_diff"] = max((jcr.sub_trans_date - psn.calc_trans_date).days + 1, 1)
                psn["sub_trans"] = jcr_dict
                ps_dict.append(get_avg_days_for_po_dict(psn))
            detailed[item_name] = ps_dict
    return detailed


def get_process_sheets(item_names):
    """
    Returns {item: submitted Process Sheets} ordered by date and name descending
    """
    ps_tab = frappe.qb.DocType("Process Sheet")
    rows = (
        frappe.qb.from_(ps_tab)
        .select(
            ps_tab.name,
            ps_tab.production_item,
            ps_tab.creation,
            ps_tab.date,
            ps_tab.quantity,
            ps_tab.produced_qty,
            ps_tab.amended_from,
            ps_tab.bom_template,
        )
        .where((ps_tab.docstatus == 1) & ps_tab.production_item.isin(item_names))
        .orderby(ps_tab.production_item)
        .orderby(ps_tab.date, order=frappe.qb.desc)
        .orderby(ps_tab.name, order=frappe.qb.desc)
        .run(as_dict=True)
    )
    ps_by_item = {}
    for row in rows:
        ps_by_item.setdefault(row.production_item, []).append(row)
    return ps_by_item


def get_ps_operations(ps_names):
    """
    Returns {Process Sheet: [operation names in the order of the operations table]}
    """
    bop = frappe.qb.DocType("BOM Operation")
    operations = {}
    for chunk in chunks(ps_names):
        rows = (
            frappe.qb.from_(bop)
            .select(bop.parent, bop.operation)
            .where((bop.parenttype == "Process Sheet") & (bop.parentfield == "operations"))
            .where(bop.parent.isin(chunk))
            .orderby(bop.parent)
            .orderby(bop.idx)
            .run(as_dict=True)
        )
        for row in rows:
            operations.setdefault(row.parent, []).append(row.operation)
    return operations


def get_lead_time_operation_flags(bom_templates):
    """
    Returns the "Don't Consider in Lead Time" flags as ({operation: flag},
    {BOM Template: {operation: sum of flags}})
    """
    op_flags = dict(frappe.get_all("Operation", fields=["name", "dont_consider_in_lead_time"],
        as_list=True))
    bt_flags = {}
    bom_templates = [bt for bt in bom_templates if bt]
    if bom_templates:
        bop = frappe.qb.DocType("BOM Operation")
        rows = (
            frappe.qb.from_(bop)
            .select(bop.parent, bop.operation, Sum(bop.dont_consider_in_lead_time))
            .where((bop.parenttype == "BOM Template RIGPL") & bop.parent.isin(bom_templates))
            .groupby(bop.parent, bop.operation)
            .run()
        )
        for parent, operation, flag in rows:
            bt_flags.setdefault(parent, {})[operation] = flag
    return op_flags, bt_flags


def get_first_jcr_for_ps(ps_names):
    """
    Returns {Process Sheet: completed submitted JCR ordered by posting date and time}
    """
    pjc = frappe.qb.DocType("Process Job Card RIGPL")
    jcr_by_ps = {}
    for chunk in chunks(ps_names):
        rows = (
            frappe.qb.from_(pjc)
            .select(pjc.name, pjc.process_sheet, pjc.operation, pjc.posting_date)
            .where((pjc.docstatus == 1) & (pjc.total_completed_qty > 0))
            .where(pjc.process_sheet.isin(chunk))
            .orderby(pjc.posting_date)
            .orderby(pjc.posting_time)
            .run(as_dict=True)
        )
        for row in rows:
            jcr_by_ps.setdefault(row.process_sheet, []).append(row)
    return jcr_by_ps


def get_jcr_for_items(item_names):
    """
    Returns {item: submitted JCR ordered by posting date and time} as sub transactions
    """
    pjc = frappe.qb.DocType("Process Job Card RIGPL")
    rows = (
        frappe.qb.from_(pjc)
        .select(
            pjc.name.as_("sub_trans_name"),
            pjc.posting_date.as_("sub_trans_date"),
            pjc.total_completed_qty.as_("sub_trans_qty"),
            pjc.production_item,
            pjc.operation,
        )
        .where((pjc.docstatus == 1) & pjc.production_item.isin(item_names))
        .orderby(pjc.posting_date)
        .orderby(pjc.posting_time)
        .run(as_dict=True)
    )
    jcr_by_item = {}
    for row in rows:
        jcr = frappe._dict({"sub_trans_name": row.sub_trans_name,
            "sub_trans_date": row.sub_trans_date, "sub_trans_type": "Process Job Card RIGPL",
            "sub_trans_qty": row.sub_trans_qty, "production_item": row.production_item,
            "operation": row.operation})
        jcr_by_item.setdefault(row.production_item, []).append(jcr)
    return jcr_by_item


def get_jcr_for_ps(psd, item_ps_list, jcr_rows, tps):
    """
    Returns a dictionary for the JCR used for a Process Sheet based on FIFO
    jcr_rows are the JCR of the last operation of the item and tps the total produced qty
    of all its Process Sheets. The rows are copied since each Process Sheet changes the qty.
    """
    sub_trans = []
    qty_compl_before_ps = get_total_completed_before_ps(psd, item_ps_list)
    ps_comp = psd.produced_qty
    jc_total = sum(flt(jcr.sub_trans_qty) for jcr in jcr_rows)
    if jc_total > tps:
        excess_qty = jc_total - tps
    else:
        excess_qty = 0
    jcr_list = copy.deepcopy(jcr_rows)
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


def get_total_completed_before_ps(psdoc, item_ps_list):
    """
    Returns the quantity completed before a Process Sheet which is completed for Last Operation
    item_ps_list are the submitted Process Sheets of the same item
    """
    return sum(flt(psn.produced_qty) for psn in item_ps_list if psn.produced_qty > 0
        and psn.date <= psdoc.date and psn.name != psdoc.name)


def get_start_date_for_psheet(psd, op_names, last_op, ps_jcr_list):
    """
    This function returns the start date for a Process Sheet Name basically if there is a lag
    between submission of Prodcess Sheet and completion of first process then it should send
    the start date as the date of first operation completion. For Ex: Is PS is submitted on 1st Jan
    but the first operation is completed on 20th Feb so item was in planning for around 50 days
    which should not be included in calculation of lead time.
    But if there is only 1 Process to be considered for the Production then it would take start
    date as the date of creation of the Process Sheet
    ps_jcr_list are the completed JCR of the Process Sheet ordered by posting date and time
    """
    first_op_name = op_names[0] if op_names else None
    if first_op_name != last_op:
        first_jcr = [jcr for jcr in ps_jcr_list if jcr.operation == first_op_name]
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
