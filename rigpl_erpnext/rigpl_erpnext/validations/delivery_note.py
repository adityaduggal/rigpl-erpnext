# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from datetime import datetime as dt
from datetime import date
from frappe.utils import getdate, get_time
from ...utils.sales_utils import check_strict_po_rules, copy_address_and_check, validate_made_to_order_items


def validate(doc, method):
    # Check if the Item has a Stock Reconciliation after the date and time or NOT.
    # if there is a Stock Reconciliation then the Update would FAIL
    # Also check if the items are from Same Price List SO as is the PL mentioned in the DN
    check_draft_dn(doc)
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


def check_draft_dn(dn_doc):
    if dn_doc.is_new() == 1:
        oth_dn = frappe.db.sql("""SELECT name FROM `tabDelivery Note` WHERE docstatus = 0 AND customer = '%s'
        AND name != '%s' """ % (dn_doc.customer, dn_doc.name), as_dict=1)
        if oth_dn:
            frappe.throw(f"{frappe.get_desk_link('Delivery Note', oth_dn[0].name)} Already In Draft for "
                         f"{dn_doc.customer} Use that Delivery Note")


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
    make_ste_for_reconciled_items(doc)
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

def make_ste_for_reconciled_items(doc):
    dn_dt_time = dt.combine(getdate(doc.posting_date), get_time(doc.posting_time))
    ste_list = []
    remarks = f"Stock Entry Due to Cancellation of DN# {doc.name} with Posting Date {doc.posting_date} on {dt.now()}"
    ste_row = frappe._dict({})
    for d in doc.items:
        sr = frappe.db.sql("""SELECT name, voucher_no FROM `tabStock Ledger Entry`
            WHERE item_code = '%s' AND CONCAT(posting_date, ' ', posting_time) > '%s'""" % (d.item_code, dn_dt_time), as_dict=1)
        if sr:
            remarks += f"\nFor Row# {d.idx} and Item: {d.item_code} there was SR: {sr[0].voucher_no}"
            ste_row["item_code"] = d.item_code
            ste_row["t_warehouse"] = d.warehouse
            ste_row["qty"] = d.qty
            ste_row["uom"] = d.uom
            ste_row["stock_uom"] = d.stock_uom
            ste_row["conversion_factor"] = d.conversion_factor
            ste_list.append(ste_row.copy())
    if ste_list:
        ste_account = frappe.db.get_value("Company", doc.company, "stock_adjustment_account")
        new_ste = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "posting_date": date.today(),
            "posting_time": (dt.now()).strftime("%H:%M:%S"),
            "difference_account": ste_account,
            "remarks": remarks,
            "items": ste_list
        })
        new_ste.flags.ignore_permissions = True
        new_ste.insert()
        new_ste.submit()
        frappe.msgprint(f"Created and Submitted {frappe.get_desk_link('Stock Entry', new_ste.name)} since \
            there was SR for Items in DN after Posting Date.\n Check STE for more details.")
