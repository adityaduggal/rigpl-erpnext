# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from ...utils.manufacturing_utils import get_bom_template_from_item


def validate(doc, method):
    # If STE linked to PO then status of Stock Entry cannot be different from PO
    # along with posting date and time
    if doc.purchase_order:
        po = frappe.get_doc("Purchase Order", doc.purchase_order)
        doc.posting_date = po.transaction_date
        doc.posting_time = '23:59:59'
    elif doc.purchase_receipt_no:
        grn = frappe.get_doc("Purchase Receipt", doc.purchase_receipt_no)
        doc.posting_date = grn.posting_date
        doc.posting_time = grn.posting_time
    else:
        for d in doc.items:
            # STE for Subcontracting WH only possible for linked with PO STE
            if d.t_warehouse:
                wht = frappe.get_doc("Warehouse", d.t_warehouse)
                if wht.is_subcontracting_warehouse == 1:
                    frappe.throw("Subcontracting Warehouse Stock Entries only possible with PO or GRN")
            if d.s_warehouse:
                whs = frappe.get_doc("Warehouse", d.s_warehouse)
                if whs.is_subcontracting_warehouse == 1:
                    frappe.throw("Subcontracting Warehouse Stock Entries only possible with PO or GRN")

    # Check if the Item has a Stock Reconciliation after the date and time or NOT.
    # if there is a Stock Reconciliation then the Update would FAIL
    for d in doc.items:
        # Get the Adjustment Account (this account is static to Stock Adjustment - RIGPL)
        d.expense_account = 'Stock Adjustment - RIGPL'
        sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE item_code = '%s' AND warehouse = '%s' 
        AND voucher_type = 'Stock Reconciliation' AND posting_date > '%s'""" % (d.item_code, d.s_warehouse,
                                                                                doc.posting_date), as_list=1)
        if sr:
            frappe.throw(("There is a Reconciliation for Item Code: {0} after the posting date in "
                          "source warehouse {1}").format(d.item_code, d.s_warehouse))
        else:
            sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE item_code = '%s' AND warehouse = '%s' 
            AND voucher_type = 'Stock Reconciliation' AND posting_date = '%s' AND posting_time >= '%s'"""
                               % (d.item_code, d.s_warehouse, doc.posting_date, doc.posting_time), as_list=1)

            if sr:
                frappe.throw(("There is a Reconciliation for Item Code: {0} after the posting time in source "
                              "warehouse {1}").format(d.item_code, d.s_warehouse))
            else:
                pass
        # Check the Stock Reconciliation for Target Warehouse as well
        sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE item_code = '%s' AND warehouse = '%s' 
        AND voucher_type = 'Stock Reconciliation' AND posting_date > '%s'""" % (d.item_code, d.t_warehouse,
                                                                                doc.posting_date), as_list=1)
        if sr:
            frappe.throw(("There is a Reconciliation for Item Code: {0} after the posting date in target "
                          "warehouse {1}").format(d.item_code, d.t_warehouse))
        else:
            sr = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE item_code = '%s' AND warehouse = '%s' 
            AND voucher_type = 'Stock Reconciliation' AND posting_date = '%s' AND posting_time >= '%s'""" % (
                d.item_code, d.t_warehouse, doc.posting_date, doc.posting_time), as_list=1)
            if sr:
                frappe.msgprint(sr)
                frappe.throw(("There is a Reconciliation for Item Code: {0} after the posting time in target "
                              "warehouse {1}").format(d.item_code, d.t_warehouse))
            else:
                pass

        # Get Stock Valuation from Item Table
        query = """SELECT valuation_rate FROM `tabItem` WHERE name = '%s' """ % d.item_code
        vr = frappe.db.sql(query, as_list=1)
        if vr[0][0] != 0 or vr[0][0]:
            d.basic_rate = vr[0][0]
            d.valuation_rate = vr[0][0]
        else:
            d.basic_rate = 1
            d.valuation_rate = 1


def on_submit(doc, method):
    allowed = 0
    user = frappe.get_user()
    if "System Manager" in user.roles:
        allowed = 1
    if doc.doctype in user.can_cancel:
        allowed = 1
    validate(doc, method)
    if not doc.flags.ignore_persmission:
        if allowed == 0:
            for it in doc.items:
                it_doc = frappe.get_doc("Item", it.item_code)
                bom_tmp = get_bom_template_from_item(it_doc)
                if bom_tmp:
                    for bt in bom_tmp:
                        frappe.msgprint("{} already has {}. So make Stock Entries via Job Card".
                                    format(frappe.get_desk_link(it_doc.doctype, it_doc.name),
                                           frappe.get_desk_link("BOM Template RIGPL", bt)))
                    frappe.throw("Not Allowed to Stock Entries for {}".
                             format(frappe.get_desk_link(it_doc.doctype, it_doc.name)))

