# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from datetime import date
from frappe.utils import nowdate, nowtime, today, add_months, flt
from .purchase_utils import get_purchase_lead_times
from .other_utils import auto_round_down, auto_round_up, round_up, get_weighted_average, \
    get_base_doc


def get_consolidate_bin(item_name):
    """
    Returns a dictionary with item_code, on_so, actual, on_po, on_indent, planned, for_prd
    for All Warehouses consolidated as one row
    """
    bin_dict = frappe.db.sql("""SELECT item_code, SUM(reserved_qty) as on_so,
        SUM(actual_qty) as actual, SUM(ordered_qty) as on_po, SUM(indented_qty) as on_indent,
        SUM(planned_qty) as planned, SUM(reserved_qty_for_production) as for_prd
        FROM `tabBin` WHERE item_code = '%s' """ % item_name, as_dict=1)
    return bin_dict


def get_qty_available_to_sell(it_doc):
    """
    Returns Qty available to Sell for an Item
    """
    qty_dict = get_quantities_for_item(it_doc)
    qty_avail = qty_dict.planned_qty + qty_dict.finished_qty + qty_dict.wip_qty + \
                qty_dict.raw_material_qty + qty_dict.dead_qty - qty_dict.on_so - \
                qty_dict.reserved_for_prd
    return qty_avail


def get_quantities_for_item(it_doc, so_item=None):
    qty_dict = frappe._dict()
    qty_dict.update({"on_so":0, "on_po":0, "on_indent":0, "planned_qty":0, "reserved_for_prd":0,
        "finished_qty":0, "wip_qty":0, "consumeable_qty":0, "raw_material_qty":0, "dead_qty":0,
        "rejected_qty":0, "calculated_rol":0, "lead_time":0, "re_order_level":0})
    if it_doc.made_to_order != 1:
        rol_dict = frappe.db.sql("""SELECT warehouse_reorder_level, warehouse_reorder_qty FROM `tabItem Reorder`
        WHERE parent = '%s' AND parenttype = '%s' AND parentfield = 'reorder_levels'""" % (it_doc.name, it_doc.doctype),
                            as_dict=1)
        if rol_dict:
            qty_dict["re_order_level"] = flt(rol_dict[0].warehouse_reorder_level)
            rol = qty_dict["re_order_level"]
        else:
            qty_dict["re_order_level"] = 0
            rol = 0
        bin_dict = frappe.db.sql("""SELECT bn.warehouse, bn.item_code, bn.reserved_qty, bn.actual_qty, bn.ordered_qty,
            bn.indented_qty, bn.planned_qty, bn.reserved_qty_for_production, bn.reserved_qty_for_sub_contract,
            wh.warehouse_type, wh.disabled FROM `tabBin` bn, `tabWarehouse` wh WHERE bn.warehouse = wh.name AND
            bn.item_code = '%s'""" % it_doc.name, as_dict=1)
        qty_dict["valuation_rate"] = flt(it_doc.valuation_rate)
        qty_dict["lead_time"] = flt(it_doc.lead_time_days) if flt(it_doc.lead_time_days) > 0 else 30
        calc_rol = get_calculated_rol(rol, flt(qty_dict["valuation_rate"]))

        qty_dict["calculated_rol"] = calc_rol
        if bin_dict:
            for d in bin_dict:
                qty_dict["on_so"] += flt(d.reserved_qty)
                qty_dict["on_po"] += flt(d.ordered_qty)
                qty_dict["on_indent"] += flt(d.indented_qty)
                qty_dict["planned_qty"] += flt(d.planned_qty)
                qty_dict["reserved_for_prd"] += flt(d.reserved_qty_for_production)

                if d.warehouse_type == 'Finished Stock':
                    qty_dict["finished_qty"] += flt(d.actual_qty)
                elif d.warehouse_type == 'Work In Progress':
                    qty_dict["wip_qty"] += flt(d.actual_qty)
                elif d.warehouse_type == 'Consumable':
                    qty_dict["consumeable_qty"] += flt(d.actual_qty)
                elif d.warehouse_type == 'Raw Material':
                    qty_dict["raw_material_qty"] += flt(d.actual_qty)
                elif d.warehouse_type == 'Dead Stock':
                    qty_dict["dead_qty"] += flt(d.actual_qty)
                elif d.warehouse_type == 'Recoverable Stock':
                    qty_dict["rejected_qty"] += flt(d.actual_qty)
                elif d.warehouse_type == 'Subcontracting':
                    qty_dict["on_po"] += flt(d.actual_qty)
    else:
        if so_item:
            on_so = frappe.db.sql("""SELECT (soi.qty - soi.delivered_qty) FROM `tabSales Order Item` soi, `tabSales Order` so
            WHERE so.docstatus=1 AND so.status != 'Closed' AND soi.qty > soi.delivered_qty
            AND soi.name = '%s'""" % so_item, as_list=1)

            on_po = frappe.db.sql("""SELECT (poi.qty - poi.received_qty) FROM `tabPurchase Order Item` poi,
            `tabPurchase Order` po
            WHERE po.docstatus=1 AND po.status != 'Closed' AND poi.qty > poi.received_qty
            AND poi.so_detail = '%s'""" % so_item, as_list=1)
            if on_so:
                qty_dict["on_so"] += on_so[0][0]
            if on_po:
                qty_dict["on_po"] += on_po[0][0]
            # frappe.msgprint(str(on_so))

    return qty_dict


def get_calculated_rol(rol, val_rate):
    rol_text = frappe.get_value("RIGPL Settings", "RIGPL Settings", "rol_multiplier")
    rol_text = rol_text.split(",")
    if not rol_text[0]:
        # Default Multipliers
        rol_text = ["5:1000", "2.5:2000", "2:2500"]
    rol_multi = []
    for d in rol_text:
        multi_dict = {}
        d=d.split(":")
        multi_dict["multiplier"] = flt(d[0])
        multi_dict["value"] = flt(d[1])
        rol_multi.append(multi_dict.copy())
    rol_multi = sorted(rol_multi, key=lambda i:i["value"])
    rol_val_rate_prod = rol * val_rate
    multiplied = 0
    for multi in rol_multi:
        if rol_val_rate_prod <= multi.get("value"):
            calc_rol = multi.get("multiplier") * rol
            multiplied = 1
    if multiplied == 0:
        calc_rol = rol
    return calc_rol


def auto_compute_rol_for_item(item_doc):
    '''
    Auto compute would check the first period calculated ROL if its within range then change
    If the ROL is out of range then check for next period till it gets within range and
    if not then set to limit. Also min ROL value should be satisfied else set the ROL to
    ZERO is min ROL value is NOT Satisfied
    '''
    rol_calc = frappe.get_value("RIGPL Settings", "RIGPL Settings", "rol_calculation")
    if not rol_calc:
        analyse_months = [12, 18, 24, 30, 36]
    else:
        analyse_months = [int(d) for d in rol_calc.split(",")]
    min_max_dict = get_min_max_rol_qty(item_doc)
    rol_period_list = []
    for period in analyse_months:
        rol_dict = get_rol_for_item(item_doc.name, period)
        rol_dict["min_allowed_rol_qty"] = min_max_dict["min_allowed_rol_qty"]
        rol_dict["max_allowed_rol_qty"] = min_max_dict["max_allowed_rol_qty"]
        rol_period_list.append(rol_dict.copy())
    new_rol = get_rol_based_on_all_periods(all_pd_rol=rol_period_list)
    return new_rol


def get_rol_based_on_all_periods(all_pd_rol):
    """
    Returns the ROL value checking comparing the existing ROL and VR with rules
    Rule for Value are as per the RIGPL settings and should never deviate more than max value
    """
    base_pd = 0
    for prd in all_pd_rol:
        base_pd += 1
        itd = frappe.get_doc("Item", prd.item_name)
        if base_pd == 1:
            base_period = prd.months
            min_rol_qty = prd.min_allowed_rol_qty
            max_rol_qty = prd.max_allowed_rol_qty
            if auto_round_down(prd.calculated_rol) > prd.ex_rol:
                base_ch_type = "increase"
                if min_rol_qty <= prd.calculated_rol <= max_rol_qty:
                    new_rol = get_actual_rol_based_on_min_rol_value(itd,
                        auto_round_down(prd.calculated_rol))
                    return new_rol, prd.months, base_ch_type
            elif auto_round_down(prd.calculated_rol) < prd.ex_rol:
                base_ch_type = "decrease"
                if min_rol_qty <= prd.calculated_rol <= max_rol_qty:
                    new_rol = get_actual_rol_based_on_min_rol_value(itd,
                        auto_round_down(prd.calculated_rol))
                    return new_rol, prd.months, base_ch_type
            else:
                base_ch_type = "same"
                new_rol = get_actual_rol_based_on_min_rol_value(itd,
                    auto_round_down(prd.calculated_rol))
                return new_rol, prd.months, base_ch_type
        base_pd += 1
        if min_rol_qty <= prd.calculated_rol <= max_rol_qty and base_pd > 1:
            new_rol = get_actual_rol_based_on_min_rol_value(itd,
                auto_round_down(prd.calculated_rol))
            if base_ch_type == "increase":
                if new_rol > prd.ex_rol:
                    return new_rol, prd.months, base_ch_type
            elif base_ch_type == "decrease":
                if new_rol < prd.ex_rol:
                    return new_rol, prd.months, base_ch_type
    if base_ch_type == "increase":
        new_rol = get_actual_rol_based_on_min_rol_value(itd, auto_round_down(max_rol_qty))
        return new_rol, "def period", base_ch_type
    else:
        new_rol = get_actual_rol_based_on_min_rol_value(itd, auto_round_down(min_rol_qty))
        return new_rol, "def period", base_ch_type


def get_min_max_rol_qty(item_doc):
    """
    Returns the Min and Max ROL Qty for an Item Doc based on RULES basically for Min Max ROL Qty
    there are 2 types of RULES:
    1. If Valuation Rate >0 then there are 3 Rules to be Followed:
        a. Fluctuation should be within the max percentage based on Value
        b. Maximum Fluctuation is also limited by the Max Fluctuation defined in Settings
        c. Minimum value of ROL should be greater than the Min defined in the Settings
    2. If Valuation Rate is Zero then qty should be within permissible percentage defined in
    settings this case is more or less simple
    min_max_dict has following keys:
        min_allowed_rol_qty, max_allowed_rol_qty
    """
    if item_doc.valuation_rate > 0:
        min_max_dict = get_min_max_qty_with_vr(item_doc)
    else:
        min_max_dict = get_min_max_qty_zero_vr(item_doc)
    return min_max_dict


def get_min_max_qty_zero_vr(item_doc):
    """
    Returns a dictionary with min and max allowed ROL qty for an item with VR===0
    If Valuation Rate is Zero then qty should be within permissible percentage defined in
    settings this case is more or less simple
    """
    mmd = frappe._dict({})
    ex_rol = get_existing_rol_for_item(item_doc.name)
    per_allowed = get_percentage_change_for_qty(ex_rol)
    if ex_rol == 0:
        mmd["min_allowed_rol_qty"] = 0
        mmd["max_allowed_rol_qty"] = per_allowed
    else:
        min_rol_qty = ex_rol * (1 - per_allowed/100)
        max_rol_qty = ex_rol * (1 + per_allowed/100)
        mmd["min_allowed_rol_qty"] = min_rol_qty
        mmd["max_allowed_rol_qty"] = max_rol_qty
    return mmd


def get_percentage_change_for_qty(ex_qty):
    """
    Returns percentage Change for Qty as per the rules defined in RIGPL Setttings
    Also would define the Case when Existing Qty = 0 then max qty in that case
    """
    per_rule = frappe.get_value("RIGPL Settings", "RIGPL Settings", "rol_qty_percentages")
    per_rule = per_rule.split(",")
    if not per_rule[0]:
        per_rule = ["1000:10, 500:20, 100:30, 50:50, 25:75, 1:100, 0:10"]
    per_rule_list = get_rule_list_frm_txt(per_rule)
    for val in per_rule_list:
        if ex_qty >= val.value:
            return val.percent
    return 100


def get_min_max_qty_with_vr(item_doc):
    """
    Returns a dictionary with min and max allowed ROL qty for an item with VR>0
    Case when VR is More than ZERO return min_max_dict based on 3 rules
        a. Fluctuation should be within the max percentage based on Value
        b. Maximum Fluctuation is also limited by the Max Fluctuation defined in Settings
        c. Minimum value of ROL should be greater than the Min defined in the Settings
    """
    mmd = frappe._dict({})
    min_rol_value = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "minimum_rol_value"))
    if min_rol_value == 0:
        min_rol_value = 10000
    max_rol_flt = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "max_rol_fluctuation"))
    if max_rol_flt == 0:
        max_rol_flt = 100000
    ex_rol = get_existing_rol_for_item(item_doc.name)
    vrate = item_doc.valuation_rate
    if ex_rol == 0:
        mmd["min_allowed_rol_qty"] = 0
        mmd["max_allowed_rol_qty"] = auto_round_up(3*min_rol_value/vrate)
    else:
        e_val = ex_rol * vrate
        per_allowed = get_percentage_change_for_value(e_val)
        if per_allowed * e_val / 100 > max_rol_flt:
            per_allowed = max_rol_flt/ e_val * 100
        min_rol = auto_round_down(ex_rol * (1 - per_allowed/100))
        max_rol = auto_round_down(ex_rol * (1 + per_allowed/100))
        mmd["min_allowed_rol_qty"] = get_actual_rol_based_on_min_rol_value(item_doc, min_rol)
        mmd["max_allowed_rol_qty"] = get_actual_rol_based_on_min_rol_value(item_doc, max_rol)
    return mmd


def get_percentage_change_for_value(ex_val):
    """
    Returns percentage for value as per the rules defined in RIGPL Setttings
    """
    per_rule = frappe.get_value("RIGPL Settings", "RIGPL Settings", "rol_value_percentages")
    per_rule = per_rule.split(",")
    if not per_rule[0]:
        per_rule = ["500000:10, 100000:20, 50000:30, 25000:50, 10000:75, 5000:100"]
    per_rule_list = get_rule_list_frm_txt(per_rule)
    for val in per_rule_list:
        if ex_val >= val.value:
            return val.percent
    return 100


def get_rule_list_frm_txt(rule_txt):
    per_rule_list = []
    for dval in rule_txt:
        multi_dict = frappe._dict({})
        dval = dval.split(":")
        multi_dict["value"] = flt(dval[0])
        multi_dict["percent"] = flt(dval[1])
        per_rule_list.append(multi_dict.copy())
    per_rule_list = sorted(per_rule_list, key=lambda i: i["value"], reverse=True)
    return per_rule_list


def update_item_rol(item_doc, rol):
    """
    Changes the Re Order Level and Re Order Qty based on New ROL Value
    """
    row_dict = frappe._dict({})
    def_wh = frappe.db.sql("""SELECT default_warehouse FROM `tabItem Default`
        WHERE parenttype = 'Item' AND parentfield = 'item_defaults'
        AND parent = '%s'""" % item_doc.name, as_dict=1)
    def_wh = def_wh[0].default_warehouse
    if item_doc.is_purchase_item == 1:
        mt_type = "Purchase"
    else:
        mt_type = "Manufacture"
    rol_table = []
    wh_group = frappe.get_value("Warehouse", def_wh, "parent_warehouse")
    row_dict["warehouse_group"] = wh_group
    row_dict["warehouse"] = def_wh
    row_dict["warehouse_reorder_level"] = get_actual_rol_based_on_min_rol_value(item_doc, rol)
    row_dict["warehouse_reorder_qty"] = get_roq_from_rol(item_doc, rol)
    row_dict["material_request_type"] = mt_type
    if item_doc.reorder_levels:
        for row in item_doc.reorder_levels:
            org_row_dict = row.__dict__
            del org_row_dict["modified"]
            del org_row_dict["modified_by"]
            for key in row_dict:
                org_row_dict[key] = row_dict[key]
            rol_table.append(org_row_dict.copy())
        item_doc.set("reorder_levels", [])
    else:
        rol_table.append(row_dict.copy())
    for row in rol_table:
        item_doc.append("reorder_levels", row)


def get_actual_rol_based_on_min_rol_value(itd, rol):
    """
    Checks if the ROL multiplied by Valuation Rate is More than Minimum ROL Value
    """
    min_rol_value = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "minimum_rol_value"))
    if min_rol_value == 0:
        min_rol_value = 10000
    if rol * itd.valuation_rate > min_rol_value:
        return rol
    else:
        if itd.valuation_rate != 0:
            return 0
        else:
            return rol


def get_roq_from_rol(item_doc, rol):
    """
    Gets the Re Order Quantity based on the ROL value of an item
    """
    min_rol_value = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "minimum_rol_value"))
    if min_rol_value == 0:
        min_rol_value = 10000
    if rol * item_doc.valuation_rate > min_rol_value:
        if rol > 1000:
            roq = round_up(rol, 200)
        elif rol > 500:
            roq = round_up(rol, 100)
        elif rol > 100:
            roq = round_up(rol, 50)
        else:
            roq = round_up(rol, 10)
    else:
        if item_doc.valuation_rate == 0:
            roq = rol
        else:
            roq = auto_round_up(min_rol_value/item_doc.valuation_rate)
    return roq


def get_rol_for_item(item_name, period=1, to_date=date.today()):
    """
    Returns a dictionary for ROL and various other values for an Item for a given period
    """
    itd = frappe.get_doc("Item", item_name)
    from_date = add_months(to_date, period * (-1))
    rol_dict = frappe._dict({})
    rol_dict["item_name"] = item_name
    rol_dict["months"] = period
    rol_dict["v_rate"] = itd.valuation_rate
    rol_dict["is_sale"] = itd.is_sales_item
    rol_dict["is_purchase"] = itd.is_purchase_item
    existing_rol = frappe.db.sql("""SELECT it.name, ir.warehouse_reorder_level as rol,
    ir.warehouse_reorder_qty as rqty FROM `tabItem` it, `tabItem Reorder` ir
    WHERE ir.parent = it.name AND ir.parenttype = 'Item' AND ir.parentfield = 'reorder_levels'
    AND disabled = 0 AND it.name = '%s'""" % item_name, as_dict=1)
    if existing_rol:
        rol_dict["ex_rol"] = existing_rol[0].rol
        rol_dict["ex_rqty"] = existing_rol[0].rqty
    else:
        rol_dict["ex_rol"] = 0
        rol_dict["ex_rqty"] = 0
    rol_dict = get_selling_based_rol(rol_dict, item_name, from_date, to_date)
    rol_dict = get_sle_based_rol(rol_dict, item_name, from_date, to_date, period)
    rol_dict = get_consumption_frm_ste(rol_dict, item_name, from_date, to_date, period)
    rol_dict = get_sr_based_rol(rol_dict, item_name, from_date, to_date, period)
    rol_dict = get_po_based_rol(rol_dict, item_name, from_date, to_date, period)

    if rol_dict["is_sale"] == 1:
        # More than 2 customers is good but 2 customers = half of Sale ROL and in Case of
        # 1 customer ROL should be ZERO
        if rol_dict["customers"] > 2:
            # Case where customers in Period is More than 2 then set the ROL
            rol_dict["calculated_rol"] = rol_dict["con_avg"] + rol_dict["sold_avg"]
        elif rol_dict["customers"] == 2:
            rol_dict["calculated_rol"] = rol_dict["con_avg"] + (rol_dict["sold_avg"]/2)
        else:
            # Half of the sold average since low customers
            rol_dict["calculated_rol"] = rol_dict["con_avg"]
    else:
        # Base the Purchase Items on PO avg instead of Consumed Average since many times no STE or
        # it could be that Item is Non-Stock Item and hence NO STE could be there. But also check
        # if the #PO is more or #STE is more Whichever is More then base on that value so if you
        # have more STE then base on consumption if more PO then base on PO
        if rol_dict["no_of_po"] >= rol_dict["no_of_ste"]:
            rol_dict["calculated_rol"] = rol_dict["po_avg"] + rol_dict["sold_avg"]
        else:
            rol_dict["calculated_rol"] = rol_dict["con_avg"] + rol_dict["sold_avg"]
    return rol_dict


def get_po_based_rol(rol_dict, item_name, from_date, to_date, period):
    """
    Adds data from purchase orders like purchased = Total Qty for which PO raised in period
    no_of_po = Total Number of POs, po_avg = Avg Qty in a period
    """
    po_data = frappe.db.sql("""SELECT SUM(sle.actual_qty) as purchased,
        COUNT(DISTINCT(sle.voucher_no)) as transactions
        FROM `tabStock Ledger Entry` sle
        WHERE sle.voucher_type IN ('Purchase Receipt', 'Purchase Invoice')
        AND sle.is_cancelled = "No" AND sle.item_code = '%s' AND posting_date >= '%s'
        AND posting_date < '%s'""" % (item_name, from_date, to_date), as_dict=1)
    rol_dict["purchased"] = flt(po_data[0].purchased)
    rol_dict["no_of_po"] = po_data[0].transactions
    rol_dict["po_avg"] = flt(po_data[0].purchased)/period
    return rol_dict


def get_consumption_frm_ste(rol_dict, item_name, from_date, to_date, period):
    """
    Adds consumption data from Stock Entries like consume = Total Qty for item consumed in period
    con_avg = Average consumption in a period, no_of_ste = No of Stock Entries
    avg_con_value = Avg Consumption Value for the item in period
    """
    consumed = frappe.db.sql("""SELECT SUM(sted.qty) as qty, COUNT(ste.name) as no_of_ste
    FROM `tabStock Entry Detail` sted, `tabStock Entry` ste
    WHERE sted.parent = ste.name AND ste.docstatus = 1 AND sted.s_warehouse IS NOT NULL
    AND (sted.t_warehouse IS NULL OR sted.t_warehouse = "") AND sted.item_code = '%s'
    AND posting_date >= '%s' AND posting_date < '%s'""" % (item_name, from_date, to_date),
    as_dict=1)
    rol_dict["consumed"] = flt(consumed[0].qty)
    rol_dict["no_of_ste"] = flt(consumed[0].no_of_ste)
    if flt(consumed[0].no_of_ste) > 2:
        rol_dict["con_avg"] = flt(consumed[0].qty)/period
    else:
        rol_dict["con_avg"] = flt(consumed[0].qty)/period/2
    rol_dict["avg_con_value"] = rol_dict["con_avg"] * rol_dict["v_rate"]
    return rol_dict


def get_sle_based_rol(rol_dict, item_name, from_date, to_date, period):
    """
    Adds Stock Ledger Based fields to the ROL dictionary like sold=total qty sold in period
    """
    sold = frappe.db.sql("""SELECT (SUM(sle.actual_qty)*-1) as sold FROM `tabStock Ledger Entry` sle
    WHERE sle.voucher_type IN ('Delivery Note', 'Sales Invoice') AND sle.is_cancelled = "No"
    AND sle.item_code = '%s' AND posting_date >= '%s'
    AND posting_date < '%s'""" % (item_name, from_date, to_date), as_dict=1)
    rol_dict["sold"] = flt(sold[0].sold)
    rol_dict["sold_avg"] = flt(sold[0].sold)/ period
    rol_dict["avg_sold_value"] = rol_dict["sold_avg"] * rol_dict["v_rate"]
    return rol_dict


def get_sr_based_rol(rol_dict, item_name, from_date, to_date, period):
    """
    Adds Stock Reconciliation based fields to rol dictionary like
    sred= Qty Removed due to Stock Reconciliation and sred average in the period
    """
    srd = frappe.db.sql("""SELECT SUM(srd.current_qty - srd.qty) as sred
        FROM `tabStock Reconciliation` sr, `tabStock Reconciliation Item` srd
        WHERE srd.parent = sr.name AND sr.docstatus = 1 AND srd.qty != srd.current_qty
        AND srd.item_code = '%s' AND sr.posting_date >= '%s' AND sr.posting_date < '%s'""" %
                       (item_name, from_date, to_date), as_dict=1)
    rol_dict["sred"] = flt(srd[0].sred)
    rol_dict["sr_avg"] = flt(srd[0].sred)/period
    rol_dict["avg_sr_value"] = rol_dict["sr_avg"] * rol_dict["v_rate"]
    return rol_dict


def get_selling_based_rol(rol_dict, item_name, from_date, to_date):
    """
    Adds selling based ROL values like no_of_so and customer = No of customers in period for
    the item
    """
    so_data = frappe.db.sql("""SELECT COUNT(DISTINCT(so.customer)) as no_of_customers ,
    COUNT(DISTINCT(so.name)) as no_of_so FROM `tabSales Order` so, `tabSales Order Item` sod
    WHERE sod.parent = so.name AND so.docstatus = 1 AND sod.item_code = '%s'
    AND so.transaction_date >= '%s' AND so.transaction_date < '%s'
    GROUP BY sod.item_code""" % (item_name, from_date, to_date), as_dict=1)
    if so_data:
        rol_dict["customers"] = so_data[0].no_of_customers
        rol_dict["no_of_so"] = so_data[0].no_of_so
    else:
        rol_dict["customers"] = 0
        rol_dict["no_of_so"] = 0
    return rol_dict


def make_sales_job_work_ste(so_no):
    """
    Utility checks Sales Order if there any Job Work Items then it would Receive the
    Items via a Stock Entry
    """
    so_doc = frappe.get_doc("Sales Order", so_no)
    ste_item_table = []
    for itm in so_doc.items:
        it_doc = frappe.get_doc("Item", itm.item_code)
        if it_doc.sales_job_work == 1:
            ste_item_table = make_ste_table(so_row=itm, ste_it_tbl=ste_item_table, it_doc=it_doc)
    if ste_item_table:
        make_stock_entry(so_no=so_no, item_table=ste_item_table)


def make_ste_table(so_row, ste_it_tbl, it_doc):
    """
    Makes Item Table for Stock Entry for Given Sales Order Row
    """
    it_dict = {}
    it_dict.setdefault("item_code", so_row.item_code)
    it_dict.setdefault("allow_zero_valuation_rate", 1)
    it_dict.setdefault("t_warehouse", it_doc.sales_job_work_warehouse)
    it_dict.setdefault("qty", so_row.qty)
    ste_it_tbl.append(it_dict.copy())
    return ste_it_tbl


def make_stock_entry(so_no, item_table):
    """
    Submit stock entry for the given item table for stock entry
    """
    ste = frappe.new_doc("Stock Entry")
    ste.flags.ignore_permissions = True
    ste.stock_entry_type = "Material Receipt"
    ste.sales_order = so_no
    ste.posting_date = nowdate()
    ste.posting_time = nowtime()
    ste.remarks = "For SO# {} Material Received for Job Work Material".format(so_no)
    for i in item_table:
        ste.append("items", i)
    ste.save()
    ste.submit()
    frappe.msgprint("Submitted {}".format(frappe.get_desk_link(ste.doctype, ste.name)))


def cancel_delete_ste_from_name(ste_name):
    """
    Cancel and delete stock entry for given stock entry name does not put it in Deleted Docs
    """
    ste_doc = frappe.get_doc("Stock Entry", ste_name)
    ste_doc.flags.ignore_permissions = True
    if ste_doc.docstatus == 1:
        ste_doc.cancel()
    frappe.delete_doc('Stock Entry', ste_name, for_reload=True)
    sle_dict = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry`
        WHERE voucher_type = 'Stock Entry' AND voucher_no = '%s'""" % ste_name, as_dict=1)
    for sle in sle_dict:
        frappe.delete_doc('Stock Ledger Entry', sle.name, for_reload=True)


def get_existing_rol_for_item(item_name):
    """
    Returns Existing ROL for Item Name
    """
    rol_dict = frappe.db.sql("""SELECT warehouse_reorder_level FROM `tabItem Reorder`
        WHERE parent = '%s' AND parenttype = 'Item'""" % (item_name), as_dict=1)
    if rol_dict:
        return flt(rol_dict[0].warehouse_reorder_level)
    else:
        return 0


def get_wh_wise_qty(item_name):
    """
    Returns a dictionary for quantities for Item in Various Warehouses
    """
    query = """SELECT bn.item_code, bn.reserved_qty as on_so, bn.actual_qty as actual, bn.warehouse,
        bn.ordered_qty as on_po, bn.planned_qty as plan, bn.projected_qty as proj,
        bn.reserved_qty_for_production as prd, wh.is_subcontracting_warehouse as subcon,
        wh.short_code as scode
        FROM `tabBin` bn, `tabWarehouse` wh
        WHERE wh.name = bn.warehouse AND bn.item_code = '%s'""" % item_name
    qty_dict = frappe.db.sql(query, as_dict=1)
    return qty_dict


def get_max_lead_times(item_name):
    """
    Returns the Maximum lead time for an Item. Basically when an item does not have a Sales Order
    or Purchase Orders then its not possible to calculate the Lead Times for an Item hence
    to overcome this problem this function checks the maximum lead time for sister items
    which are within the same Template
    """
    itd = frappe.get_doc("Item", item_name)
    if itd.variant_of and itd.has_variants != 1:
        max_ld_time = frappe.db.sql("""SELECT MAX(lead_time_days) as max_lead_time FROM `tabItem`
            WHERE variant_of = '%s' AND disabled = 0 LIMIT 1""" % (itd.variant_of), as_dict=1)
        return flt(max_ld_time[0].max_lead_time)
    else:
        print("Either Item has Variants or Is Not a Variant of Any Template in this Case Return 0")
        return 0


def get_item_lead_time(item_name, frm_dt=None, to_dt=None):
    """
    This function gets the lead time for an item based on Purchase or Manufacture
    """
    ldt_dict = frappe._dict({})
    itd = frappe.get_doc("Item", item_name)
    if itd.is_sales_item == 1:
        # Items which are in Sales should be taken from the DN status
        ldt_dict = get_selling_lead_times(item_name, frm_dt=frm_dt, to_dt=to_dt)
    elif itd.is_purchase_item == 1:
        # Check the days between the PO and GRN if ZERO days then dont consider that
        # set for calculations
        ldt_dict = get_purchase_lead_times(item_name, frm_dt=frm_dt, to_dt=to_dt)
    else:
        # Check which items are there and device a formula for that as well.
        ldt_dict["avg_days_wt"] = 0
        print(f"Item {item_name} is neither Sales nor Purchase so Lead Time is Set to 0")
    return ldt_dict


def get_selling_lead_times(item_name, frm_dt=None, to_dt=None):
    """
    Returns a dict with item_name and lead_times based on Sales Orders to DN times
    Lead Time Dict would have following keys: item_name, avg_days, no_of_trans, total_qty
    min_days, max_days, avg_days_wt, tot_qty
    avg_days_wt is the weighted average delivery time
    """
    day_wise = []
    ldt_dict = frappe._dict({})
    ldt_dict["item_name"] = item_name
    so_dict = get_so_for_item(item_name, frm_dt=frm_dt, to_dt=to_dt)
    ldt_dict["no_of_trans"] = len(so_dict)
    for sod in so_dict:
        avg_days = get_avg_days_for_so(sod)
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
        day_wise.append(get_avg_days_for_so(sod).copy())
    avg_days_wt, tot_qty = get_weighted_average(list_of_data=day_wise, avg_key="avg_days",
        wt_key="tot_qty")
    ldt_dict["avg_days_wt"] = avg_days_wt
    ldt_dict["tot_qty"] = tot_qty
    return ldt_dict


def get_so_for_item(it_name, frm_dt=None, to_dt=None):
    cond = ""
    if frm_dt:
        cond += " AND so.transaction_date >= '%s'" % frm_dt
    if to_dt:
        cond += " AND so.transaction_date <= '%s'" % to_dt

    so_dict = frappe.db.sql("""SELECT so.name as so_no, sod.name, so.transaction_date,
        sod.qty, sod.idx
        FROM `tabSales Order` so, `tabSales Order Item` sod
        WHERE so.docstatus = 1 AND sod.parent = so.name AND sod.item_code = '%s'
        AND sod.delivered_qty > 0 %s
        ORDER BY so.transaction_date DESC, sod.name LIMIT 100""" % (it_name, cond), as_dict=1)
    return so_dict


def get_avg_days_for_so(so_dict):
    avg_days_dict = frappe._dict({})
    avg_days, days_wt, tot_qty = 0, 0, 0
    query = """SELECT dn.name as dn, dni.name, dn.posting_date, dni.qty
        FROM `tabDelivery Note` dn, `tabDelivery Note Item` dni
        WHERE dn.name = dni.parent AND dni.so_detail = '%s'
        ORDER BY dn.posting_date DESC""" % so_dict.name
    dn_dict = frappe.db.sql(query, as_dict=1)
    for dn_no in dn_dict:
        base_dn = get_base_doc("Delivery Note", dn_no.dn)
        dnd = frappe.get_doc("Delivery Note", base_dn)
        dn_no["posting_date"] = dnd.posting_date
        days = (dn_no.posting_date - so_dict.transaction_date).days
        if days > 0:
            tot_qty += dn_no.qty
            days_wt += days * dn_no.qty
    if tot_qty > 0:
        avg_days = auto_round_up(days_wt / tot_qty)
    else:
        avg_days = 0
    avg_days_dict["tot_qty"] = tot_qty
    avg_days_dict["avg_days"] = avg_days
    return avg_days_dict
