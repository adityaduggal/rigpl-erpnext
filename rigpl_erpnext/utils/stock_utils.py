# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import nowdate, nowtime


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
