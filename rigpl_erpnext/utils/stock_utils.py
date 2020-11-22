# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import nowdate, nowtime, today, add_months, flt
from .other_utils import auto_round_down,auto_round_up, round_up


def auto_compute_rol_for_item(item_doc):
    # Auto compute would check the first period calculated ROL if its within range then change
    # If the ROL is out of range then check for next period till it gets within range and if not then set to limit
    # Also min ROL value should be satisfied else set the ROL to ZERO is min ROL value is NOT Satisfied
    analyse_months = [3, 6, 9, 12, 24]
    rol_period_list = []
    for period in analyse_months:
        rol_dict = get_rol_for_item(item_doc.name, period)
        rol_period_list.append(rol_dict.copy())

    for d in rol_period_list:
        if d.get("months") == analyse_months[0]:
            # Only base on the latest data other data is just for reference and comparison
            # print(str(d) + '\n\n')
            if d.get("ex_rol") > 100:
                # Difference cannot be more than 10%
                if 1.1 * d.get("ex_rol") >= d.get("calculated_rol") >= 0.9 * d.get("ex_rol"):
                    if d.get("ex_rol") != auto_round_down(d.get('calculated_rol')):
                        update_item_rol(item_doc, auto_round_down(d.get("calculated_rol")))
                    break
                else:
                    for oth in rol_period_list:
                        found = 0
                        if oth.get("months") != d.get("months"):
                            if 1.1 * d.get("ex_rol") >= d.get("calculated_rol") >= 0.9 * d.get("ex_rol"):
                                found = 1
                                if d.get("ex_rol") != auto_round_down(d.get('calculated_rol')):
                                    update_item_rol(item_doc, auto_round_down(d.get("calculated_rol")))
                                break
                        if found == 0:
                            if d.get("ex_rol") > d.get("calculated_rol"):
                                print(f"Reducing ROL by 10% for {item_doc.name} to "
                                      f"{auto_round_down(0.9 * d.get('ex_rol'))}")
                                update_item_rol(item_doc, auto_round_down(0.9 * d.get('ex_rol')))
                            else:
                                print(f"Increasing ROL by 10% for {item_doc.name} to "
                                      f"{auto_round_down(1.1 * d.get('ex_rol'))}")
                                update_item_rol(item_doc, auto_round_down(1.1 * d.get('ex_rol')))
                            break

            elif d.get("ex_rol") > 50:
                # Difference cannot be more than 50%
                if 1.5 * d.get("ex_rol") >= d.get("calculated_rol") >= 0.5 * d.get("ex_rol"):
                    if d.get("ex_rol") != auto_round_down(d.get('calculated_rol')):
                        update_item_rol(item_doc, auto_round_down(d.get("calculated_rol")))
                    break
                else:
                    for oth in rol_period_list:
                        found = 0
                        if oth.get("months") != d.get("months"):
                            if 1.5 * d.get("ex_rol") >= d.get("calculated_rol") >= 0.5 * d.get("ex_rol"):
                                found = 1
                                if d.get("ex_rol") != auto_round_down(d.get('calculated_rol')):
                                    update_item_rol(item_doc, auto_round_down(d.get("calculated_rol")))
                                break
                        if found == 0:
                            if d.get("ex_rol") > d.get("calculated_rol"):
                                print(f"Reducing ROL by 50% for {item_doc.name} to "
                                      f"{auto_round_down(0.5 * d.get('ex_rol'))}")
                                update_item_rol(item_doc, auto_round_down(0.5 * d.get('ex_rol')))
                            else:
                                print(f"Increasing ROL by 50% for {item_doc.name} to "
                                      f"{auto_round_down(1.5 * d.get('ex_rol'))}")
                                update_item_rol(item_doc, auto_round_down(1.5 * d.get('ex_rol')))
                            break
            elif d.get("ex_rol") > 0:
                # Difference cannot be more than 100%
                if 2 * d.get("ex_rol") >= d.get("calculated_rol"):
                    if d.get("ex_rol") != auto_round_down(d.get('calculated_rol')):
                        update_item_rol(item_doc, auto_round_down(d.get("calculated_rol")))
                    break
                else:
                    for oth in rol_period_list:
                        found = 0
                        if oth.get("months") != d.get("months"):
                            if 2 * d.get("ex_rol") >= d.get("calculated_rol"):
                                found = 1
                                print(f"Would automatically change the ROL to "
                                      f"{auto_round_down(d.get('calculated_rol'))}")
                                if d.get("ex_rol") != auto_round_down(d.get('calculated_rol')):
                                    update_item_rol(item_doc, auto_round_down(d.get("calculated_rol")))
                                break
                        if found == 0:
                            if d.get("ex_rol") > d.get("calculated_rol"):
                                print(f"Reducing ROL by 50% for {item_doc.name} to "
                                      f"{auto_round_down(0.5 * d.get('ex_rol'))}")
                                update_item_rol(item_doc, auto_round_down(0.5 * d.get('ex_rol')))
                            else:
                                print(f"Increasing ROL by 50% for {item_doc.name} to "
                                      f"{auto_round_down(1.5 * d.get('ex_rol'))}")
                                update_item_rol(item_doc, auto_round_down(1.5 * d.get('ex_rol')))
                            break
            else:
                if d.get("calculated_rol") > 10:
                    new_rol = 10
                    print(f"Increasing ROL for {item_doc.name} to {new_rol}")
                    update_item_rol(item_doc, new_rol)
                elif d.get("calculated_rol") > 1:
                    new_rol = auto_round_down(d.get("calculated_rol"))
                    print(f"Increasing ROL for {item_doc.name} to {new_rol}")
                    update_item_rol(item_doc, new_rol)


def update_item_rol(item_doc, rol):
    rol_dict = {}
    def_wh = frappe.db.sql("""SELECT default_warehouse FROM `tabItem Default` WHERE parenttype = 'Item' AND
    parentfield = 'item_defaults' AND parent = '%s'""" % item_doc.name, as_dict=1)
    if def_wh:
        rol_dict["warehouse_group"] = frappe.get_value("Warehouse", def_wh[0].default_warehouse, "parent_warehouse")
        rol_dict["warehouse"] = def_wh[0].default_warehouse
    if item_doc.is_purchase_item == 1:
        rol_dict["material_request_type"] = "Purchase"
    else:
        rol_dict["material_request_type"] = "Manufacture"
    item_doc.reorder_levels = []
    rol_value = rol * flt(item_doc.valuation_rate)
    # Set the Value of ROL and ROQ
    rol_dict["warehouse_reorder_level"] = auto_round_down(rol)
    rol_dict["warehouse_reorder_qty"] = get_roq_from_rol(item_doc, rol)
    item_doc.append("reorder_levels", rol_dict.copy())


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
    AND it.name = '%s'""" %(item_name), as_dict=1)
    if existing_rol:
        rol_dict["ex_rol"] =existing_rol[0].rol
        rol_dict["ex_rqty"] = existing_rol[0].rqty
    else:
        rol_dict["ex_rol"] = 0
        rol_dict["ex_rqty"] = 0
    print(f"Processing {item_name} with existing ROL= {rol_dict.ex_rol} and Valuation Rate = {rol_dict.v_rate}")
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
    rol_dict["con_avg"] = flt(consumed[0].qty)/period
    rol_dict["avg_con_value"] = rol_dict["con_avg"] * rol_dict["v_rate"]

    sr = frappe.db.sql("""SELECT SUM(srd.current_qty - srd.qty) as sred FROM `tabStock Reconciliation` sr, 
    `tabStock Reconciliation Item` srd WHERE srd.parent = sr.name AND sr.docstatus = 1 AND srd.qty != srd.current_qty 
    AND srd.item_code = '%s' AND sr.posting_date >= '%s' AND sr.posting_date < '%s'""" %
                       (item_name, from_date, to_date), as_dict=1)
    rol_dict["sred"] = flt(sr[0].sred)
    rol_dict["sr_avg"] = flt(sr[0].sred)/period
    rol_dict["avg_sr_value"] = rol_dict["sr_avg"] * rol_dict["v_rate"]


    po_data = frappe.db.sql("""SELECT SUM(sle.actual_qty) as purchased, COUNT(DISTINCT(sle.voucher_no)) as transactions 
    FROM `tabStock Ledger Entry` sle WHERE sle.voucher_type IN ('Purchase Receipt', 'Purchase Invoice') AND sle.is_cancelled = "No" 
    AND sle.item_code = '%s' AND posting_date >= '%s' AND posting_date < '%s'""" %
                            (item_name, from_date, to_date), as_dict=1)
    rol_dict["purchased"] = flt(po_data[0].purchased)
    rol_dict["no_of_po"] = po_data[0].transactions
    rol_dict["po_avg"] = flt(po_data[0].purchased)/period
    if rol_dict["is_sale"] == 1:
        if rol_dict["customers"] > 1:
            # Case where customers in Period is More than 1 then set the ROL
            rol_dict["calculated_rol"] = rol_dict["con_avg"] + rol_dict["sold_avg"]
        else:
            # Now since there is only 1 or less customers then check if item is used majorly in Consumption then set
            # Else don't set the ROL
            if rol_dict["con_avg"] > rol_dict["sold_avg"] + 10:
                rol_dict["calculated_rol"] = rol_dict["con_avg"] + rol_dict["sold_avg"]
            else:
                rol_dict["calculated_rol"] = 0
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


def cancel_delete_ste_from_name(ste_name, trash_can=1):
    if trash_can == 0:
        ignore_on_trash = True
    else:
        ignore_on_trash = False

    ste_doc = frappe.get_doc("Stock Entry", ste_name)
    ste_doc.flags.ignore_permissions = True
    if ste_doc.docstatus == 1:
        ste_doc.cancel()
    frappe.delete_doc('Stock Entry', ste_name, for_reload=ignore_on_trash)
    sle_dict = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE voucher_type = 'Stock Entry' AND 
        voucher_no = '%s'""" % ste_name, as_dict=1)
    for sle in sle_dict:
        frappe.delete_doc('Stock Ledger Entry', sle.name, for_reload=ignore_on_trash)


