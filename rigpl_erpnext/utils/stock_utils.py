# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import math
import statistics
from datetime import date
import frappe
from frappe.query_builder.functions import Count, Max, Sum
from frappe.utils import nowdate, nowtime, add_months, flt, getdate, now
from pypika.terms import Criterion
from .batch_write_utils import bulk_insert_rows, bulk_insert_versions, clear_document_cache
from .item_attribute_utils import chunks
from .other_utils import auto_round_down, auto_round_up, round_up


def get_indented_qty(item_code, warehouse=None):
    """
    Returns the indented quantity as per the Material Requests
    """
    wh_cond = ""
    if warehouse:
        wh_cond += f" AND mri.warehouse = '{warehouse}'"
    ind_dict = frappe.db.sql(f"""SELECT SUM(mri.qty - mri.ordered_qty) as ind_qty
        FROM `tabMaterial Request` mr, `tabMaterial Request Item` mri
        WHERE mri.parent = mr.name AND mr.docstatus = 1 AND mr.status != 'Stopped'
        AND mri.qty > mri.ordered_qty AND mri.item_code = '{item_code}'
        {wh_cond}""", as_dict=1)
    return flt(ind_dict[0].ind_qty)


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
    """
    Returns a Dictionary for Item Doc and its quantities on Sales Order, On Indent etc
    """
    qty_dict = frappe._dict()
    qty_dict.update({"on_so":0, "on_po":0, "on_indent":0, "planned_qty":0, "reserved_for_prd":0,
        "finished_qty":0, "wip_qty":0, "consumeable_qty":0, "raw_material_qty":0, "dead_qty":0,
        "rejected_qty":0, "calculated_rol":0, "lead_time":0, "re_order_level":0})
    if it_doc.made_to_order != 1:
        rol_dict = frappe.db.sql("""SELECT warehouse_reorder_level, warehouse_reorder_qty
            FROM `tabItem Reorder` WHERE parent = '%s' AND parenttype = '%s'
            AND parentfield = 'reorder_levels'""" % (it_doc.name, it_doc.doctype), as_dict=1)
        if rol_dict:
            qty_dict["re_order_level"] = flt(rol_dict[0].warehouse_reorder_level)
            rol = qty_dict["re_order_level"]
        else:
            qty_dict["re_order_level"] = 0
            rol = 0
        bin_dict = frappe.db.sql("""SELECT bn.warehouse, bn.item_code, bn.reserved_qty,
            bn.actual_qty, bn.ordered_qty, bn.indented_qty, bn.planned_qty,
            bn.reserved_qty_for_production, bn.reserved_qty_for_sub_contract, wh.warehouse_type,
            wh.disabled FROM `tabBin` bn, `tabWarehouse` wh WHERE bn.warehouse = wh.name AND
            bn.item_code = '%s'""" % it_doc.name, as_dict=1)
        qty_dict["valuation_rate"] = flt(it_doc.valuation_rate)
        qty_dict["lead_time"] = flt(it_doc.lead_time_days) if flt(it_doc.lead_time_days) > 0 else 30
        calc_rol = get_calculated_rol(rol, flt(qty_dict["valuation_rate"]))

        qty_dict["calculated_rol"] = calc_rol
        if bin_dict:
            for bnd in bin_dict:
                qty_dict["on_so"] += flt(bnd.reserved_qty)
                qty_dict["on_po"] += flt(bnd.ordered_qty)
                qty_dict["on_indent"] += flt(bnd.indented_qty)
                qty_dict["planned_qty"] += flt(bnd.planned_qty)
                qty_dict["reserved_for_prd"] += flt(bnd.reserved_qty_for_production)

                if bnd.warehouse_type == 'Finished Stock':
                    qty_dict["finished_qty"] += flt(bnd.actual_qty)
                elif bnd.warehouse_type == 'Work In Progress':
                    qty_dict["wip_qty"] += flt(bnd.actual_qty)
                elif bnd.warehouse_type == 'Consumable':
                    qty_dict["consumeable_qty"] += flt(bnd.actual_qty)
                elif bnd.warehouse_type == 'Raw Material':
                    qty_dict["raw_material_qty"] += flt(bnd.actual_qty)
                elif bnd.warehouse_type == 'Dead Stock':
                    qty_dict["dead_qty"] += flt(bnd.actual_qty)
                elif bnd.warehouse_type == 'Recoverable Stock':
                    qty_dict["rejected_qty"] += flt(bnd.actual_qty)
                elif bnd.warehouse_type == 'Subcontracting':
                    qty_dict["on_po"] += flt(bnd.actual_qty)
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
    return compute_rol_for_items(get_items_for_rol([item_doc.name]))[item_doc.name]


# Order frequency classes for the ROL of sales items, checked in order:
# (name, minimum Sales Orders in the last 12 months, months of data, days in a demand bucket)
ROL_FREQUENCY_CLASSES = (
    ("Fast", 53, 6, 7),
    ("Regular", 13, 12, 7),
    ("Occasional", 4, 24, 30),
)
# Items with fewer orders, or with all orders from fewer customers, are Rare
ROL_MIN_CUSTOMERS = 3
ROL_RARE_MONTHS = 24
DEFAULT_LEAD_TIME_DAYS = 30


def compute_rol_for_items(items, to_date=None):
    """
    Returns {item name: (new_rol, basis, change type)} like auto_compute_rol_for_item, for the
    item rows from get_items_for_rol with a fixed number of queries for each chunk.
    Sales items get their ROL from how often they are ordered (get_sales_rol), other items
    from their purchases or consumption in the periods of RIGPL Settings.
    """
    to_date = getdate(to_date or date.today())
    sales_items = [itm for itm in items if itm.is_sales_item == 1]
    other_items = [itm for itm in items if itm.is_sales_item != 1]
    new_rols = compute_rol_for_items_by_period(other_items, to_date) if other_items else {}
    if not sales_items:
        return new_rols

    names = [itm.name for itm in sales_items]
    order_lines = get_order_lines_for_items(names, add_months(to_date, -ROL_RARE_MONTHS), to_date)
    consumption = {
        months: get_consumption_for_items(names, add_months(to_date, -months), to_date)
        for months in {cls[2] for cls in ROL_FREQUENCY_CLASSES} | {ROL_RARE_MONTHS}
    }
    for itm in sales_items:
        calc_rol, basis = get_sales_rol(itm, order_lines.get(itm.name, []), consumption, to_date)
        new_rols[itm.name] = limit_rol_change(itm, calc_rol, basis)
    return new_rols


def get_sales_rol(itm, order_lines, consumption, to_date):
    """
    Returns (calculated ROL, basis) for a sales item based on how often it is ordered:
    - Fast, Regular and Occasional items: the demand in the lead time plus safety stock
      (RIGPL Settings ROL Safety Factor x the variation of demand in the lead time)
    - Rare items: the median order qty
    Big orders count only up to Big Order Multiple x the median order qty, so one big order
    does not make the ROL jump. Consumption with Stock Entries in the lead time is added.
    """
    year_ago = add_months(to_date, -12)
    last_year = [line for line in order_lines if line.transaction_date >= year_ago]
    no_of_orders = len({line.sales_order for line in last_year})
    no_of_customers = len({line.customer for line in last_year})
    lead_time = flt(itm.lead_time_days) or DEFAULT_LEAD_TIME_DAYS

    rol_class = None
    if no_of_customers >= ROL_MIN_CUSTOMERS:
        rol_class = next((cls for cls in ROL_FREQUENCY_CLASSES if no_of_orders >= cls[1]), None)
    if rol_class:
        name, _min_orders, months, bucket_days = rol_class
        from_date = add_months(to_date, -months)
        qtys = cap_big_orders([(line.transaction_date, line.stock_qty) for line in order_lines
            if line.transaction_date >= from_date])
        daily_demand, daily_sigma = get_daily_demand(qtys, from_date, to_date, bucket_days)
        safety_factor = flt(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings",
            "rol_safety_factor")) or 1.65
        calc_rol = daily_demand * lead_time + safety_factor * daily_sigma * math.sqrt(lead_time)
        basis = f"{name} ({no_of_orders} Orders in 12 months) on {months} months Data"
    else:
        months = ROL_RARE_MONTHS
        qtys = cap_big_orders([(line.transaction_date, line.stock_qty) for line in order_lines])
        calc_rol = statistics.median([qty for _dt, qty in qtys]) if qtys else 0
        basis = (f"Rare ({no_of_orders} Orders from {no_of_customers} Customers in 12 months) "
            f"on Median Order of {months} months")

    con = consumption[months].get(itm.name)
    if con:
        con_days = max((to_date - add_months(to_date, -months)).days, 1)
        calc_rol += flt(con.qty) / con_days * lead_time
    return calc_rol, basis


def cap_big_orders(qtys):
    """
    Returns [(date, qty)] where a qty above Big Order Multiple x the median qty is capped
    """
    if not qtys:
        return []
    multiple = flt(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings",
        "big_order_multiple")) or 5
    cap = statistics.median([flt(qty) for _dt, qty in qtys]) * multiple
    return [(dt, min(flt(qty), cap)) for dt, qty in qtys]


def get_daily_demand(qtys, from_date, to_date, bucket_days):
    """
    Returns (average demand per day, standard deviation of the demand per day) for
    [(date, qty)] in the period, from the demand in buckets of bucket_days. Empty buckets
    count as 0 demand.
    """
    days = max((getdate(to_date) - getdate(from_date)).days, 1)
    buckets = [0.0] * max(math.ceil(days / bucket_days), 1)
    for dt, qty in qtys:
        idx = min((getdate(dt) - getdate(from_date)).days // bucket_days, len(buckets) - 1)
        buckets[idx] += qty
    daily_demand = sum(buckets) / days
    daily_sigma = statistics.pstdev(buckets) / math.sqrt(bucket_days)
    return daily_demand, daily_sigma


def limit_rol_change(itm, calc_rol, basis):
    """
    Returns (new_rol, basis, change type) with the change from the existing ROL limited by the
    qty and value rules of RIGPL Settings (get_min_max_rol_qty) and the Minimum ROL Value
    """
    min_max_dict = get_min_max_rol_qty(itm, ex_rol=itm.existing_rol)
    new_rol = auto_round_down(calc_rol)
    if new_rol > itm.existing_rol:
        ch_type = "increase"
    elif new_rol < itm.existing_rol:
        ch_type = "decrease"
    else:
        ch_type = "same"
    if new_rol > min_max_dict["max_allowed_rol_qty"]:
        new_rol = auto_round_down(min_max_dict["max_allowed_rol_qty"])
    elif new_rol < min_max_dict["min_allowed_rol_qty"]:
        new_rol = auto_round_down(min_max_dict["min_allowed_rol_qty"])
    return get_actual_rol_based_on_min_rol_value(itm, new_rol), basis, ch_type


def get_order_lines_for_items(item_names, from_date, to_date):
    """
    Returns {item_code: submitted Sales Order lines in the period} with sales_order, customer,
    transaction_date and stock_qty
    """
    so = frappe.qb.DocType("Sales Order")
    sod = frappe.qb.DocType("Sales Order Item")
    order_lines = {}
    for chunk in chunks(item_names):
        rows = (
            frappe.qb.from_(sod)
            .join(so)
            .on(sod.parent == so.name)
            .select(
                sod.item_code,
                so.name.as_("sales_order"),
                so.customer,
                so.transaction_date,
                sod.stock_qty,
            )
            .where((so.docstatus == 1) & sod.item_code.isin(chunk))
            .where((so.transaction_date >= from_date) & (so.transaction_date < to_date))
            .run(as_dict=True)
        )
        for row in rows:
            order_lines.setdefault(row.item_code, []).append(row)
    return order_lines


def compute_rol_for_items_by_period(items, to_date=None):
    """
    Returns {item name: (new_rol, period, change type)} for items which are not sold, from their
    purchases or consumption in the periods of RIGPL Settings (ROL Calculation)
    """
    rol_calc = frappe.get_cached_value("RIGPL Settings", "RIGPL Settings", "rol_calculation")
    if not rol_calc:
        analyse_months = [12, 18, 24, 30, 36]
    else:
        analyse_months = [int(d) for d in rol_calc.split(",")]
    rol_by_period = {
        period: get_rol_data_for_items(items, period, to_date) for period in analyse_months
    }
    new_rols = {}
    for itm in items:
        min_max_dict = get_min_max_rol_qty(itm, ex_rol=itm.existing_rol)
        rol_period_list = []
        for period in analyse_months:
            rol_dict = rol_by_period[period][itm.name]
            rol_dict["min_allowed_rol_qty"] = min_max_dict["min_allowed_rol_qty"]
            rol_dict["max_allowed_rol_qty"] = min_max_dict["max_allowed_rol_qty"]
            rol_period_list.append(rol_dict.copy())
        new_rol, period, ch_type = get_rol_based_on_all_periods(all_pd_rol=rol_period_list,
            item=itm)
        new_rols[itm.name] = (new_rol, f"{period} months Data", ch_type)
    return new_rols


def get_rol_based_on_all_periods(all_pd_rol, item=None):
    """
    Returns the ROL value checking comparing the existing ROL and VR with rules
    Rule for Value are as per the RIGPL settings and should never deviate more than max value
    item needs the valuation_rate and is read from the database when not given
    """
    base_pd = 0
    itd = item or frappe.get_doc("Item", all_pd_rol[0].item_name)
    for prd in all_pd_rol:
        base_pd += 1
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


def get_min_max_rol_qty(item_doc, ex_rol=None):
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
    if ex_rol is None:
        ex_rol = get_existing_rol_for_item(item_doc.name)
    if item_doc.valuation_rate > 0:
        min_max_dict = get_min_max_qty_with_vr(item_doc, ex_rol)
    else:
        min_max_dict = get_min_max_qty_zero_vr(item_doc, ex_rol)
    return min_max_dict


def get_min_max_qty_zero_vr(item_doc, ex_rol):
    """
    Returns a dictionary with min and max allowed ROL qty for an item with VR===0
    If Valuation Rate is Zero then qty should be within permissible percentage defined in
    settings this case is more or less simple
    """
    mmd = frappe._dict({})
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
    per_rule = frappe.get_cached_value("RIGPL Settings", "RIGPL Settings", "rol_qty_percentages")
    per_rule = per_rule.split(",")
    if not per_rule[0]:
        per_rule = ["1000:10, 500:20, 100:30, 50:50, 25:75, 1:100, 0:10"]
    per_rule_list = get_rule_list_frm_txt(per_rule)
    for val in per_rule_list:
        if ex_qty >= val.value:
            return val.percent
    return 100


def get_min_max_qty_with_vr(item_doc, ex_rol):
    """
    Returns a dictionary with min and max allowed ROL qty for an item with VR>0
    Case when VR is More than ZERO return min_max_dict based on 3 rules
        a. Fluctuation should be within the max percentage based on Value
        b. Maximum Fluctuation is also limited by the Max Fluctuation defined in Settings
        c. Minimum value of ROL should be greater than the Min defined in the Settings
    """
    mmd = frappe._dict({})
    min_rol_value = flt(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings", "minimum_rol_value"))
    if min_rol_value == 0:
        min_rol_value = 10000
    max_rol_flt = flt(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings", "max_rol_fluctuation"))
    if max_rol_flt == 0:
        max_rol_flt = 100000
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
    per_rule = frappe.get_cached_value("RIGPL Settings", "RIGPL Settings", "rol_value_percentages")
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


REORDER_FIELDS = (
    "name",
    "creation",
    "modified",
    "modified_by",
    "owner",
    "docstatus",
    "parent",
    "parentfield",
    "parenttype",
    "idx",
    "warehouse_group",
    "warehouse",
    "warehouse_reorder_level",
    "warehouse_reorder_qty",
    "material_request_type",
)
REORDER_VALUE_FIELDS = REORDER_FIELDS[10:]


def set_item_reorder_levels(item_rols):
    """
    Writes the Re Order Level for [(item row from get_items_for_rol, rol)] like
    update_item_rol and Item.save() would, with one query for each 1000 rows, and adds the
    Versions. Returns the names of the items without a Default Warehouse, which are skipped.
    """
    timestamp, user = now(), frappe.session.user
    rows, diffs, no_default_wh = [], {}, []
    for itm, rol in item_rols:
        if not itm.default_warehouses:
            no_default_wh.append(itm.name)
            continue
        new_values = {
            "warehouse_group": itm.warehouse_group,
            # Item validate (validate_reoder) sets the warehouse of the last Item Default
            "warehouse": itm.default_warehouses[-1],
            "warehouse_reorder_level": get_actual_rol_based_on_min_rol_value(itm, rol),
            "warehouse_reorder_qty": get_roq_from_rol(itm, rol),
            "material_request_type": "Purchase" if itm.is_purchase_item == 1 else "Manufacture",
        }
        diff = {"row_changed": [], "added": []}
        existing_rows = itm.reorder_rows or [
            frappe._dict(name=frappe.generate_hash(length=10), idx=1, is_new=True)
        ]
        for i, row in enumerate(existing_rows):
            rows.append(
                (row.name, timestamp, timestamp, user, user, 0, itm.name, "reorder_levels", "Item",
                row.idx) + tuple(new_values.values())
            )
            if row.is_new:
                diff["added"].append(["reorder_levels", dict(name=row.name, **new_values)])
                continue
            changed = [[field, row.get(field), value] for field, value in new_values.items()
                if row.get(field) != value]
            if changed:
                diff["row_changed"].append(["reorder_levels", i, row.name, changed])
        diffs[itm.name] = diff

    bulk_insert_rows("Item Reorder", REORDER_FIELDS, rows,
        update_fields=("modified", "modified_by") + REORDER_VALUE_FIELDS)
    clear_document_cache("Item", diffs)
    bulk_insert_versions("Item", diffs)
    return no_default_wh


def get_actual_rol_based_on_min_rol_value(itd, rol):
    """
    Checks if the ROL multiplied by Valuation Rate is More than Minimum ROL Value
    """
    min_rol_value = flt(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings", "minimum_rol_value"))
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
    min_rol_value = flt(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings", "minimum_rol_value"))
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


def get_rol_for_item(item_name, period=1, to_date=None):
    """
    Returns a dictionary for ROL and various other values for an Item for a given period
    """
    return get_rol_data_for_items(get_items_for_rol([item_name]), period, to_date)[item_name]


def get_items_for_rol(item_names):
    """
    Returns the Item rows for the ROL calculation in the order of item_names: name, disabled,
    valuation_rate, is_sales_item, is_purchase_item, lead_time_days, existing_rol, reorder_rows,
    default_warehouses and warehouse_group. Uses 4 queries for each chunk of items.
    """
    it_tab = frappe.qb.DocType("Item")
    ro_tab = frappe.qb.DocType("Item Reorder")
    idf_tab = frappe.qb.DocType("Item Default")
    wh_tab = frappe.qb.DocType("Warehouse")
    items = []
    for chunk in chunks(item_names):
        item_dict = {
            row.name: row
            for row in frappe.qb.from_(it_tab)
            .select(
                it_tab.name,
                it_tab.disabled,
                it_tab.valuation_rate,
                it_tab.is_sales_item,
                it_tab.is_purchase_item,
                it_tab.lead_time_days,
            )
            .where(it_tab.name.isin(chunk))
            .run(as_dict=True)
        }
        for itm in item_dict.values():
            itm.update({"existing_rol": None, "reorder_rows": [], "default_warehouses": []})
        reorder_rows = (
            frappe.qb.from_(ro_tab)
            .select(
                ro_tab.name,
                ro_tab.parent,
                ro_tab.parentfield,
                ro_tab.idx,
                ro_tab.warehouse,
                ro_tab.warehouse_group,
                ro_tab.warehouse_reorder_level,
                ro_tab.warehouse_reorder_qty,
                ro_tab.material_request_type,
            )
            .where(ro_tab.parent.isin(chunk) & (ro_tab.parenttype == "Item"))
            .orderby(ro_tab.parent)
            .orderby(ro_tab.idx)
            .run(as_dict=True)
        )
        for row in reorder_rows:
            itm = item_dict[row.parent]
            if itm.existing_rol is None:
                itm.existing_rol = flt(row.warehouse_reorder_level)
            if row.parentfield == "reorder_levels":
                itm.reorder_rows.append(row)
        default_rows = (
            frappe.qb.from_(idf_tab)
            .select(idf_tab.parent, idf_tab.default_warehouse)
            .where(idf_tab.parent.isin(chunk) & (idf_tab.parenttype == "Item"))
            .where(idf_tab.parentfield == "item_defaults")
            .orderby(idf_tab.parent)
            .orderby(idf_tab.idx)
            .run(as_dict=True)
        )
        for row in default_rows:
            item_dict[row.parent].default_warehouses.append(row.default_warehouse)
        warehouses = {wh for itm in item_dict.values() for wh in itm.default_warehouses if wh}
        wh_groups = {}
        if warehouses:
            wh_groups = dict(
                frappe.qb.from_(wh_tab)
                .select(wh_tab.name, wh_tab.parent_warehouse)
                .where(wh_tab.name.isin(list(warehouses)))
                .run()
            )
        for name in chunk:
            itm = item_dict.get(name)
            if not itm:
                continue
            itm.existing_rol = flt(itm.existing_rol)
            if itm.default_warehouses:
                itm.warehouse_group = wh_groups.get(itm.default_warehouses[0])
            items.append(itm)
    return items


def get_rol_data_for_items(items, period=1, to_date=None, from_date=None):
    """
    Returns {item name: ROL dictionary} for a given period like get_rol_for_item, for the
    item rows from get_items_for_rol with 5 grouped queries for each chunk of items.
    period is the number of months used for the averages. from_date is by default the
    period before to_date.
    """
    to_date = to_date or date.today()
    from_date = from_date or add_months(to_date, period * (-1))
    rol_data = {}
    for start in range(0, len(items), 1000):
        item_rows = items[start : start + 1000]
        names = [itm.name for itm in item_rows]
        selling = get_selling_data_for_items(names, from_date, to_date)
        sold = get_sle_qty_for_items(names, ["Delivery Note", "Sales Invoice"], from_date,
            to_date)
        consumed = get_consumption_for_items(names, from_date, to_date)
        sred = get_sr_qty_for_items(names, from_date, to_date)
        purchased = get_sle_qty_for_items(names, ["Purchase Receipt", "Purchase Invoice"],
            from_date, to_date)
        for itm in item_rows:
            rol_dict = frappe._dict({})
            rol_dict["item_name"] = itm.name
            rol_dict["months"] = period
            rol_dict["v_rate"] = itm.valuation_rate
            rol_dict["is_sale"] = itm.is_sales_item
            rol_dict["is_purchase"] = itm.is_purchase_item
            ex_row = itm.reorder_rows[0] if itm.reorder_rows and not itm.disabled else None
            rol_dict["ex_rol"] = ex_row.warehouse_reorder_level if ex_row else 0
            rol_dict["ex_rqty"] = ex_row.warehouse_reorder_qty if ex_row else 0

            so_data = selling.get(itm.name)
            rol_dict["customers"] = so_data.no_of_customers if so_data else 0
            rol_dict["no_of_so"] = so_data.no_of_so if so_data else 0

            sold_qty = sold.get(itm.name, frappe._dict())
            rol_dict["sold"] = flt(sold_qty.qty) * -1 if sold_qty.qty else 0
            rol_dict["sold_avg"] = rol_dict["sold"] / period
            rol_dict["avg_sold_value"] = rol_dict["sold_avg"] * rol_dict["v_rate"]

            con = consumed.get(itm.name, frappe._dict())
            rol_dict["consumed"] = flt(con.qty)
            rol_dict["no_of_ste"] = flt(con.no_of_ste)
            if flt(con.no_of_ste) > 2:
                rol_dict["con_avg"] = flt(con.qty)/period
            else:
                rol_dict["con_avg"] = flt(con.qty)/period/2
            rol_dict["avg_con_value"] = rol_dict["con_avg"] * rol_dict["v_rate"]

            rol_dict["sred"] = flt(sred.get(itm.name))
            rol_dict["sr_avg"] = rol_dict["sred"]/period
            rol_dict["avg_sr_value"] = rol_dict["sr_avg"] * rol_dict["v_rate"]

            po_data = purchased.get(itm.name, frappe._dict())
            rol_dict["purchased"] = flt(po_data.qty)
            rol_dict["no_of_po"] = po_data.transactions or 0
            rol_dict["po_avg"] = flt(po_data.qty)/period

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
            rol_data[itm.name] = rol_dict
    return rol_data


def get_sle_qty_for_items(item_names, voucher_types, from_date, to_date):
    """
    Returns {item_code: frappe._dict(qty, transactions)} from the Stock Ledger for the voucher
    types in the period. transactions is the number of distinct vouchers.
    """
    sle = frappe.qb.DocType("Stock Ledger Entry")
    rows = (
        frappe.qb.from_(sle)
        .select(
            sle.item_code,
            Sum(sle.actual_qty).as_("qty"),
            Count(sle.voucher_no).distinct().as_("transactions"),
        )
        .where(sle.voucher_type.isin(voucher_types) & (sle.is_cancelled == 0))
        .where(sle.item_code.isin(item_names))
        .where((sle.posting_date >= from_date) & (sle.posting_date < to_date))
        .groupby(sle.item_code)
        .run(as_dict=True)
    )
    return {row.item_code: row for row in rows}


def get_consumption_for_items(item_names, from_date, to_date):
    """
    Returns {item_code: frappe._dict(qty, no_of_ste)} for the qty consumed with Stock Entries
    (source warehouse only) in the period
    """
    ste = frappe.qb.DocType("Stock Entry")
    sted = frappe.qb.DocType("Stock Entry Detail")
    rows = (
        frappe.qb.from_(sted)
        .join(ste)
        .on(sted.parent == ste.name)
        .select(sted.item_code, Sum(sted.qty).as_("qty"), Count(ste.name).as_("no_of_ste"))
        .where((ste.docstatus == 1) & sted.s_warehouse.isnotnull())
        .where(sted.t_warehouse.isnull() | (sted.t_warehouse == ""))
        .where(sted.item_code.isin(item_names))
        .where((ste.posting_date >= from_date) & (ste.posting_date < to_date))
        .groupby(sted.item_code)
        .run(as_dict=True)
    )
    return {row.item_code: row for row in rows}


def get_sr_qty_for_items(item_names, from_date, to_date):
    """
    Returns {item_code: qty removed with Stock Reconciliations in the period}
    """
    sr = frappe.qb.DocType("Stock Reconciliation")
    srd = frappe.qb.DocType("Stock Reconciliation Item")
    rows = (
        frappe.qb.from_(srd)
        .join(sr)
        .on(srd.parent == sr.name)
        .select(srd.item_code, Sum(srd.current_qty - srd.qty))
        .where((sr.docstatus == 1) & (srd.qty != srd.current_qty))
        .where(srd.item_code.isin(item_names))
        .where((sr.posting_date >= from_date) & (sr.posting_date < to_date))
        .groupby(srd.item_code)
        .run()
    )
    return dict(rows)


def get_selling_data_for_items(item_names, from_date, to_date):
    """
    Returns {item_code: frappe._dict(no_of_customers, no_of_so)} for the submitted Sales
    Orders in the period
    """
    so = frappe.qb.DocType("Sales Order")
    sod = frappe.qb.DocType("Sales Order Item")
    rows = (
        frappe.qb.from_(so)
        .join(sod)
        .on(sod.parent == so.name)
        .select(
            sod.item_code,
            Count(so.customer).distinct().as_("no_of_customers"),
            Count(so.name).distinct().as_("no_of_so"),
        )
        .where((so.docstatus == 1) & sod.item_code.isin(item_names))
        .where((so.transaction_date >= from_date) & (so.transaction_date < to_date))
        .groupby(sod.item_code)
        .run(as_dict=True)
    )
    return {row.item_code: row for row in rows}


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
    return get_wh_wise_qty_for_items([item_name]).get(item_name, [])


def get_reorder_levels(items):
    """
    Returns {item: highest warehouse reorder level}
    """
    ro = frappe.qb.DocType("Item Reorder")
    rol_dict = {}
    for chunk in chunks(items):
        rows = (
            frappe.qb.from_(ro)
            .select(ro.parent, Max(ro.warehouse_reorder_level))
            .where(ro.parent.isin(chunk) & (ro.parenttype == "Item"))
            .groupby(ro.parent)
            .run()
        )
        rol_dict.update(dict(rows))
    return rol_dict


def get_wh_wise_qty_for_items(items, non_zero=False):
    """
    Returns {item_code: [Bin quantities per Warehouse]} for many items, one query per chunk.
    With non_zero, leave out the Bins where all quantities are 0 (most Bins are).
    """
    bin_tab = frappe.qb.DocType("Bin")
    wh_tab = frappe.qb.DocType("Warehouse")
    qty_dict = {}
    qty_fields = (
        bin_tab.actual_qty,
        bin_tab.reserved_qty,
        bin_tab.ordered_qty,
        bin_tab.planned_qty,
        bin_tab.reserved_qty_for_production,
    )
    for chunk in chunks(items):
        query = (
            frappe.qb.from_(bin_tab)
            .join(wh_tab)
            .on(wh_tab.name == bin_tab.warehouse)
            .select(
                bin_tab.item_code,
                bin_tab.reserved_qty.as_("on_so"),
                bin_tab.actual_qty.as_("actual"),
                bin_tab.warehouse,
                bin_tab.ordered_qty.as_("on_po"),
                bin_tab.planned_qty.as_("plan"),
                bin_tab.projected_qty.as_("proj"),
                bin_tab.reserved_qty_for_production.as_("prd"),
                wh_tab.is_subcontracting_warehouse.as_("subcon"),
                wh_tab.short_code.as_("scode"),
            )
            .where(bin_tab.item_code.isin(chunk))
        )
        if non_zero:
            query = query.where(Criterion.any([field != 0 for field in qty_fields]))
        for row in query.run(as_dict=True):
            qty_dict.setdefault(row.item_code, []).append(row)
    return qty_dict


def get_template_max_lead_times(templates, exclude_items=()):
    """
    Returns {template: maximum lead time of its enabled variants} like get_max_lead_times for
    many templates. exclude_items are left out, for example the items without lead time data.
    """
    it_tab = frappe.qb.DocType("Item")
    max_lead_times = {}
    exclude_items = list(exclude_items)
    for chunk in chunks(templates):
        query = (
            frappe.qb.from_(it_tab)
            .select(it_tab.variant_of, Max(it_tab.lead_time_days))
            .where(it_tab.variant_of.isin(chunk) & (it_tab.disabled == 0))
            .groupby(it_tab.variant_of)
        )
        if exclude_items:
            query = query.where(it_tab.name.notin(exclude_items))
        max_lead_times.update({template: flt(max_lt) for template, max_lt in query.run()})
    return max_lead_times


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
