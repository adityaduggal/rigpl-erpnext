# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from rigpl_erpnext.utils.sales_utils import check_strict_po_rules, copy_address_and_check, validate_made_to_order_items


def validate(doc, method):
    # Check if the Item has a Stock Reconciliation after the date and time or NOT.
    # if there is a Stock Reconciliation then the Update would FAIL
    # Also check if the items are from Same Price List SO as is the PL mentioned in the DN
    check_strict_po_rules(doc)
    copy_address_and_check(doc)
    check_price_list(doc, method)
    for dnd in doc.get("items"):
        if dnd.against_sales_order:
            so = frappe.get_doc("Sales Order", dnd.against_sales_order)
            sod = frappe.get_doc("Sales Order Item", dnd.so_detail)
            dnd.price_list = sod.price_list
            sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE item_code = '%s' 
            AND warehouse = '%s' AND voucher_type = 'Stock Reconciliation' AND posting_date > '%s'""" %
                               (dnd.item_code, dnd.warehouse, doc.posting_date), as_list=1)
            if sr:
                frappe.throw("There is a Reconciliation for Item Code: {0} after "
                             "the posting date".format(dnd.item_code))
            else:
                sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE item_code = '%s' 
                AND warehouse = '%s' AND voucher_type = 'Stock Reconciliation' AND posting_date = '%s' 
                AND posting_time >= '%s'""" %
                                   (dnd.item_code, dnd.warehouse, doc.posting_date, doc.posting_time), as_list=1)
                if sr:
                    frappe.throw("There is a Reconciliation for Item Code: {0} after the posting time".
                                 format(dnd.item_code))
        else:
            frappe.throw("Delivery Note {} not against any Sales Order at Row {}".format(doc.name, dnd.idx))


def check_price_list(doc, method):
    for it in doc.items:
        if it.so_detail:
            sod_doc = frappe.get_doc("Sales Order Item", it.so_detail)
            it.price_list = sod_doc.price_list


def on_submit(doc, method):
    validate_made_to_order_items(doc)
    for dnd in doc.get("items"):
        if dnd.so_detail and dnd.against_sales_order:
            so = frappe.get_doc("Sales Order", dnd.against_sales_order)
            sod = frappe.get_doc("Sales Order Item", dnd.so_detail)
            if so.track_trial == 1:
                query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
                name = frappe.db.sql(query, as_list=1)
                tt = frappe.get_doc("Trial Tracking", name[0][0])
                if tt:
                    frappe.db.set(tt, 'status', 'Material Ready')
                    frappe.msgprint('{0}{1}'.format("Updated Status of Trial No: ", name[0][0]))


def on_cancel(doc, method):
    for dnd in doc.get("items"):
        # Code to update the status in Trial Tracking
        if dnd.so_detail and dnd.against_sales_order:
            so = frappe.get_doc("Sales Order", dnd.against_sales_order)
            sod = frappe.get_doc("Sales Order Item", dnd.so_detail)
            if so.track_trial == 1:
                query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
                name = frappe.db.sql(query, as_list=1)
                tt = frappe.get_doc("Trial Tracking", name[0][0])
                if tt:
                    frappe.db.set(tt, 'status', 'In Production')
                    frappe.msgprint('{0}{1}'.format("Updated Status of Trial No: ", name[0][0]))
