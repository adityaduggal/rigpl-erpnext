# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from frappe.utils import nowdate, nowtime, today, add_months, flt
from .other_utils import auto_round_down, auto_round_up, round_up


def get_consolidate_bin(item_name):
    bin_dict = frappe.db.sql("""SELECT item_code, SUM(reserved_qty) as on_so, SUM(actual_qty) as actual, 
    SUM(ordered_qty) as on_po, SUM(indented_qty) as on_indent, SUM(planned_qty) as planned, 
    SUM(reserved_qty_for_production) as for_prd
    FROM `tabBin` WHERE item_code = '%s' """ % item_name, as_dict=1)
    return bin_dict


def auto_compute_rol_for_item(item_doc):
    # Auto compute would check the first period calculated ROL if its within range then change
    # If the ROL is out of range then check for next period till it gets within range and if not then set to limit
    # Also min ROL value should be satisfied else set the ROL to ZERO is min ROL value is NOT Satisfied
    changes_made = 0
    analyse_months = [3, 6, 12, 18, 24]
    rol_period_list = []
    for period in analyse_months:
        rol_dict = get_rol_for_item(item_doc.name, period)
        rol_period_list.append(rol_dict.copy())
    for d in rol_period_list:
        vr = item_doc.valuation_rate
        e_rol = d.get("ex_rol")
        e_val = e_rol * vr
        if d.get("months") == analyse_months[0]:
            n_rol = auto_round_down(d.get("calculated_rol"))
            n_val = n_rol * item_doc.valuation_rate
            diff_val = abs(n_val - e_val)
            if diff_val > 0:
                # Check based on Difference Value
                changes_made, n_rol, percent = return_rol_based_val(item_doc, e_rol, n_rol)
                if changes_made == 0:
                    found = 0
                    for oth in rol_period_list:
                        if d.months != oth.months:
                            np_rol = auto_round_down(oth.calculated_rol)
                            changes_made, nt_rol, percent = return_rol_based_val(item_doc, e_rol, np_rol)
                            if changes_made == 1:
                                found = 1
                                if n_rol > e_rol:
                                    n_rol = auto_round_down(e_rol * ((100 + percent) / 100))
                                else:
                                    n_rol = auto_round_down(e_rol * ((100 - percent) / 100))
                                break
                    if found == 0:
                        # Difference in Valuation is Greater than MAX Allowed for All Periods hence make the
                        # Changes as per the Max Allowed Value
                        changes_made, n_rol, percent = return_rol_based_val(item_doc, e_rol, n_rol)
                else:
                    # Found the correct New ROL and Hence Exit the Loop
                    break
            else:
                # Check if Valuation Rate is ZERO if ZERO then new ROL based on Qty
                if vr == 0:
                    changes_made, n_rol, percent = return_rol_based_qty(e_rol, n_rol)
                    if changes_made == 0:
                        found = 0
                        for oth in rol_period_list:
                            if d.months != oth.months:
                                np_rol = auto_round_down(oth.calculated_rol)
                                changes_made, nt_rol, percent = return_rol_based_qty(e_rol, np_rol)
                                if changes_made == 1:
                                    found = 1
                                    if n_rol > e_rol:
                                        n_rol = auto_round_down(e_rol * ((100 + percent) / 100))
                                    else:
                                        n_rol = auto_round_down(e_rol * ((100 - percent) / 100))
                                    break
    if changes_made == 1:
        update_item_rol(item_doc, n_rol)
        print(f"Changing ROL for {item_doc.name} from {e_rol} to {n_rol} Difference = {n_rol - e_rol} "
              f"and Value Difference = {(n_rol - e_rol) * vr}")
    return changes_made


def return_rol_based_val(itd, e_rol, n_rol):
    """
    Check and Return ROL value based on Total Value ideally the values should be taken from settings but
    But hardcoded are as below if Value>500k then max allowed change is 100k or 10% whichever is lower
    if value>100k then max allowed change is 20%, value>50k then 30%, value>25k then 50%, value>10k then 100%
    """
    changes_made = 0
    max_rol_diff = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "max_rol_fluctuation"))
    if max_rol_diff == 0:
        max_rol_diff = 100000
    val_txt = frappe.get_value("RIGPL Settings", "RIGPL Settings", "rol_value_percentages")
    val_txt = val_txt.split(",")
    if not val_txt[0]:
        val_txt = ["500000:10, 100000:20, 50000:30, 25000:50, 10000:75, 5000:100"]
    vr = itd.valuation_rate
    e_val = vr * e_rol
    n_val = vr * n_rol
    val_diff = abs(n_val - e_val)
    if val_diff > max_rol_diff:
        if n_val > e_val:
            n_rol = auto_round_down((e_val + max_rol_diff) / vr)
        else:
            n_rol = auto_round_down((e_val - max_rol_diff) / vr)
        n_val = vr * n_rol
    val_list = []
    for d in val_txt:
        multi_dict = frappe._dict({})
        d = d.split(":")
        multi_dict["value"] = flt(d[0])
        multi_dict["percent"] = flt(d[1])
        val_list.append(multi_dict.copy())
    val_list = sorted(val_list, key=lambda i: i["value"], reverse=True)
    for d in val_list:
        percent = d.percent
        if e_val >= d.value:
            max_val = e_val * ((100 + d.percent) / 100)
            min_val = e_val * ((100 - d.percent) / 100)
            if min_val <= n_val <= max_val:
                changes_made = 1
                break
            else:
                if n_rol > e_rol:
                    n_rol = auto_round_down(e_rol * ((100 + d.percent) / 100))
                else:
                    n_rol = auto_round_down(e_rol * ((100 - d.percent) / 100))
                break
    return changes_made, n_rol, percent


def return_rol_based_qty(e_rol, n_rol):
    """
    Check and return the ROL value based on Qty. Basically if the VR is ZERO then allow Existing ROL to fluctuate as
    ROL>1000 allowed 10% change, ROL>500 allowed 20% change, ROL>100 allowed 30% change, ROL>50 allowed 40% change
    ROL>10 allowed 50% change and if ROL>1 then 100% change allowed in case Existing ROL=0 then max newROL = 10
    """
    changes_made = 0
    max_val_for_zero_rol = 10

    qty_txt = frappe.get_value("RIGPL Settings", "RIGPL Settings", "rol_qty_percentages")
    qty_txt = qty_txt.split(",")
    if not qty_txt[0]:
        val_txt = ["1000:10, 500:20, 100:30, 50:50, 25:75, 1:100, 0:10"]
    val_list = []
    for d in qty_txt:
        multi_dict = frappe._dict({})
        d = d.split(":")
        if flt(d[0]) != 0:
            multi_dict["qty"] = flt(d[0])
            multi_dict["percent"] = flt(d[1])
            val_list.append(multi_dict.copy())
        else:
            max_val_for_zero_rol = flt(d[1])
    val_list = sorted(val_list, key=lambda i: i["qty"], reverse=True)
    for d in val_list:
        percent = d.percent
        if e_rol >= d.qty != 0:
            max_qty = e_rol * ((100 + d.percent) / 100)
            min_qty = e_rol * ((100 - d.percent) / 100)
            if min_qty <= n_rol <= max_qty:
                changes_made = 1
                break
            else:
                if n_rol > e_rol:
                    n_rol = auto_round_down(e_rol * ((100 + d.percent) / 100))
                else:
                    n_rol = auto_round_down(e_rol * ((100 - d.percent) / 100))
                break
        elif e_rol == 0:
            max_qty = max_val_for_zero_rol
            if n_rol > e_rol:
                changes_made = 1
                if n_rol > max_qty:
                    n_rol = max_qty
                else:
                    n_rol = auto_round_down(n_rol)

    return changes_made, n_rol, percent


def update_item_rol(item_doc, rol):
    rol_dict = {}
    def_wh = frappe.db.sql("""SELECT default_warehouse FROM `tabItem Default` WHERE parenttype = 'Item' AND
    parentfield = 'item_defaults' AND parent = '%s'""" % item_doc.name, as_dict=1)
    row_dict = frappe._dict({})
    rol_table = []
    for row in item_doc.reorder_levels:
        row_dict = row.__dict__
        if def_wh:
            row_dict["warehouse_group"] = frappe.get_value("Warehouse", def_wh[0].default_warehouse, "parent_warehouse")
            row_dict["warehouse"] = def_wh[0].default_warehouse
        if item_doc.is_purchase_item == 1:
            rol_dict["material_request_type"] = "Purchase"
        else:
            rol_dict["material_request_type"] = "Manufacture"
    # Set the Value of ROL and ROQ
        row_dict["warehouse_reorder_level"] = get_actual_rol_based_on_value(item_doc, auto_round_down(rol))
        row_dict["warehouse_reorder_qty"] = get_roq_from_rol(item_doc, rol)
        del row_dict["modified"]
        del row_dict["modified_by"]
        rol_table.append(row_dict.copy())
    item_doc.set("reorder_levels", [])
    for d in rol_table:
        item_doc.append("reorder_levels", d)


def get_actual_rol_based_on_value(itd, rol):
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
            roq = 0
        else:
            roq = auto_round_up(min_rol_value/item_doc.valuation_rate)
    return roq


def get_rol_for_item(item_name, period=1, to_date=today()):
    # Period is in months
    itd = frappe.get_doc("Item", item_name)
    from_date = add_months(to_date, period * (-1))
    rol_dict = frappe._dict({})
    rol_dict["item_name"] = item_name
    rol_dict["months"] = period
    rol_dict["v_rate"] = itd.valuation_rate
    rol_dict["is_sale"] = itd.is_sales_item
    rol_dict["is_purchase"] = itd.is_purchase_item
    existing_rol = frappe.db.sql("""SELECT it.name, ir.warehouse_reorder_level as rol, 
    ir.warehouse_reorder_qty as rqty FROM `tabItem` it, `tabItem Reorder` ir WHERE ir.parent = it.name 
    AND ir.parenttype = 'Item' AND ir.parentfield = 'reorder_levels' AND disabled = 0 
    AND it.name = '%s'""" % item_name, as_dict=1)
    if existing_rol:
        rol_dict["ex_rol"] = existing_rol[0].rol
        rol_dict["ex_rqty"] = existing_rol[0].rqty
    else:
        rol_dict["ex_rol"] = 0
        rol_dict["ex_rqty"] = 0
    sold = frappe.db.sql("""SELECT (SUM(sle.actual_qty)*-1) as sold FROM `tabStock Ledger Entry` sle 
    WHERE sle.voucher_type IN ('Delivery Note', 'Sales Invoice') AND sle.is_cancelled = "No" AND sle.item_code = '%s'
    AND posting_date >= '%s' AND posting_date < '%s'""" % (item_name, from_date, to_date), as_dict=1)
    rol_dict["sold"] = flt(sold[0].sold)
    rol_dict["sold_avg"] = flt(sold[0].sold)/ period
    rol_dict["avg_sold_value"] = rol_dict["sold_avg"] * rol_dict["v_rate"]

    so_data = frappe.db.sql("""SELECT COUNT(DISTINCT(so.customer)) as no_of_customers , 
    COUNT(DISTINCT(so.name)) as no_of_so FROM `tabSales Order` so, `tabSales Order Item` sod 
    WHERE sod.parent = so.name AND so.docstatus = 1 AND sod.item_code = '%s' AND so.transaction_date >= '%s' 
    AND so.transaction_date < '%s' GROUP BY sod.item_code""" % (item_name, from_date, to_date), as_dict=1)
    if so_data:
        rol_dict["customers"] = so_data[0].no_of_customers
        rol_dict["no_of_so"] = so_data[0].no_of_so
    else:
        rol_dict["customers"] = 0
        rol_dict["no_of_so"] = 0

    consumed = frappe.db.sql("""SELECT SUM(sted.qty) as qty, COUNT(ste.name) as no_of_ste 
    FROM `tabStock Entry Detail` sted, `tabStock Entry` ste 
    WHERE sted.parent = ste.name AND ste.docstatus = 1 AND sted.s_warehouse IS NOT NULL 
    AND (sted.t_warehouse IS NULL OR sted.t_warehouse = "") AND sted.item_code = '%s' AND posting_date >= '%s' 
    AND posting_date < '%s'""" % (item_name, from_date, to_date), as_dict=1)
    rol_dict["consumed"] = flt(consumed[0].qty)
    rol_dict["no_of_ste"] = flt(consumed[0].no_of_ste)
    if flt(consumed[0].no_of_ste) > 2:
        rol_dict["con_avg"] = flt(consumed[0].qty)/period
    else:
        rol_dict["con_avg"] = flt(consumed[0].qty)/period/2
    rol_dict["avg_con_value"] = rol_dict["con_avg"] * rol_dict["v_rate"]

    sr = frappe.db.sql("""SELECT SUM(srd.current_qty - srd.qty) as sred FROM `tabStock Reconciliation` sr, 
    `tabStock Reconciliation Item` srd WHERE srd.parent = sr.name AND sr.docstatus = 1 AND srd.qty != srd.current_qty 
    AND srd.item_code = '%s' AND sr.posting_date >= '%s' AND sr.posting_date < '%s'""" %
                       (item_name, from_date, to_date), as_dict=1)
    rol_dict["sred"] = flt(sr[0].sred)
    rol_dict["sr_avg"] = flt(sr[0].sred)/period
    rol_dict["avg_sr_value"] = rol_dict["sr_avg"] * rol_dict["v_rate"]

    po_data = frappe.db.sql("""SELECT SUM(sle.actual_qty) as purchased, COUNT(DISTINCT(sle.voucher_no)) as transactions 
    FROM `tabStock Ledger Entry` sle WHERE sle.voucher_type IN ('Purchase Receipt', 'Purchase Invoice') 
    AND sle.is_cancelled = "No" AND sle.item_code = '%s' AND posting_date >= '%s' AND posting_date < '%s'""" %
                            (item_name, from_date, to_date), as_dict=1)
    rol_dict["purchased"] = flt(po_data[0].purchased)
    rol_dict["no_of_po"] = po_data[0].transactions
    rol_dict["po_avg"] = flt(po_data[0].purchased)/period
    if rol_dict["is_sale"] == 1:
        # More than 2 customers is good but 2 customers = half of Sale ROL and in Case of 1 customer 1/4
        if rol_dict["customers"] > 2:
            # Case where customers in Period is More than 2 then set the ROL
            rol_dict["calculated_rol"] = rol_dict["con_avg"] + rol_dict["sold_avg"]
        elif rol_dict["customers"] == 2:
            rol_dict["calculated_rol"] = rol_dict["con_avg"] + (rol_dict["sold_avg"]/2)
        else:
            # Half of the sold average since low customers
            rol_dict["calculated_rol"] = (rol_dict["sold_avg"]/4) + rol_dict["con_avg"]
    else:
        # Base the Purchase Items on PO avg instead of Consumed Average since many times no STE or it could be that
        # Item is Non-Stock Item and hence NO STE could be there. But also check if the #PO is more or #STE is more
        # Whichever is More then base on that value so if you have more STE then base on consumption if more PO then
        # base on PO
        if rol_dict["no_of_po"] >= rol_dict["no_of_ste"]:
            rol_dict["calculated_rol"] = rol_dict["po_avg"] + rol_dict["sold_avg"]
        else:
            rol_dict["calculated_rol"] = rol_dict["con_avg"] + rol_dict["sold_avg"]

    return rol_dict


def make_sales_job_work_ste(so_no):
    # Utility checks Sales Order if there any Job Work Items then it would Receive the Items via a Stock Entry
    so_doc = frappe.get_doc("Sales Order", so_no)
    ste_item_table = []
    for it in so_doc.items:
        it_doc = frappe.get_doc("Item", it.item_code)
        if it_doc.sales_job_work == 1:
            ste_item_table = make_ste_table(so_row=it, ste_it_tbl=ste_item_table, it_doc=it_doc)
    if ste_item_table:
        make_stock_entry(so_no=so_no, item_table=ste_item_table)


def make_ste_table(so_row, ste_it_tbl, it_doc):
    it_dict = {}
    it_dict.setdefault("item_code", so_row.item_code)
    it_dict.setdefault("allow_zero_valuation_rate", 1)
    it_dict.setdefault("t_warehouse", it_doc.sales_job_work_warehouse)
    it_dict.setdefault("qty", so_row.qty)
    ste_it_tbl.append(it_dict.copy())
    return ste_it_tbl


def make_stock_entry(so_no, item_table):
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
    ste_doc = frappe.get_doc("Stock Entry", ste_name)
    ste_doc.flags.ignore_permissions = True
    if ste_doc.docstatus == 1:
        ste_doc.cancel()
    frappe.delete_doc('Stock Entry', ste_name, for_reload=True)
    sle_dict = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE voucher_type = 'Stock Entry' AND 
        voucher_no = '%s'""" % ste_name, as_dict=1)
    for sle in sle_dict:
        frappe.delete_doc('Stock Ledger Entry', sle.name, for_reload=True)
