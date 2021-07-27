# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import datetime as dt
from frappe.utils import getdate, get_time
from ...utils.manufacturing_utils import get_bom_template_from_item


def validate(doc, method):
    # If STE linked to PO then status of Stock Entry cannot be different from PO
    # along with posting date and time
    def_stk_adj_acc = frappe.get_value("Company", doc.company, "stock_adjustment_account")
    if doc.purchase_order:
        po = frappe.get_doc("Purchase Order", doc.purchase_order)
        doc.posting_date = po.transaction_date
        doc.posting_time = '23:59:59'
    elif doc.purchase_receipt_no:
        grn = frappe.get_doc("Purchase Receipt", doc.purchase_receipt_no)
        doc.posting_date = grn.posting_date
        doc.posting_time = grn.posting_time
    elif doc.process_job_card:
        jc = frappe.get_doc("Process Job Card RIGPL", doc.process_job_card)
        doc.posting_date = jc.posting_date
        doc.posting_time = jc.posting_time

    # Check if the Item has a Stock Reconciliation after the date and time or NOT.
    # if there is a Stock Reconciliation then the Update would FAIL
    sr_list = []
    sr_row = frappe._dict({})
    for d in doc.items:
        # Get the Adjustment Account (this account is static to Default Account in Company Settings)
        d.expense_account = def_stk_adj_acc
        ste_dt_time = dt.datetime.combine(getdate(doc.posting_date), get_time(doc.posting_time))
        query = """SELECT name, voucher_no, CONCAT(posting_date, ' ', posting_time) as ptime
        FROM `tabStock Ledger Entry` WHERE item_code = '%s' AND warehouse = '%s'
        AND voucher_type = 'Stock Reconciliation'
        AND CONCAT(posting_date, ' ', posting_time) >= '%s' LIMIT 1""" % (d.item_code, d.s_warehouse, ste_dt_time)
        sr = frappe.db.sql(query, as_dict=1)
        if sr:
            sr_row["idx"] = d.idx
            sr_row["ic"] = d.item_code
            sr_row["wh"] = d.s_warehouse
            sr_row["srn"] = sr[0].voucher_no
            sr_row["ptime"] = sr[0].ptime
            sr_list.append(sr_row.copy())
        # Check the Stock Reconciliation for Target Warehouse as well
        query = """SELECT name, voucher_no, CONCAT(posting_date, ' ', posting_time) as ptime
        FROM `tabStock Ledger Entry` WHERE item_code = '%s' AND warehouse = '%s'
        AND voucher_type = 'Stock Reconciliation'
        AND CONCAT(posting_date, ' ', posting_time) >= '%s' LIMIT 1""" % (d.item_code, d.t_warehouse, ste_dt_time)
        sr = frappe.db.sql(query, as_dict=1)
        if sr:
            sr_row["idx"] = d.idx
            sr_row["ic"] = d.item_code
            sr_row["wh"] = d.s_warehouse
            sr_row["srn"] = sr[0].voucher_no
            sr_row["ptime"] = sr[0].ptime
            sr_list.append(sr_row.copy())
    if sr_list:
        for d in sr_list:
            frappe.msgprint(f"In Row# {d.idx} and Item: {d.ic} for {d.wh} there is Stock Reconciliation \
                {d.srn} at {d.ptime}")
        frappe.throw(f"Cannot Proceed")

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
    if doc.flags.ignore_persmission == False:
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

