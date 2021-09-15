# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import datetime as dt
from frappe.utils import getdate, get_time
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from ...utils.manufacturing_utils import get_bom_template_from_item


def validate(doc, method):
    """
    Validates Stock Entry on Saving
    """
    update_ste_date(doc)
    update_valuation_rate(doc)
    check_stock_recon(doc)



def on_submit(doc, method):
    """
    Only allow submission rights to System Manager or Role which can cancel the document
    """
    validate(doc, method)
    allowed = 0
    if doc.flags.ignore_persmission is False:
        user = frappe.get_user()
        if "System Manager" in user.roles:
            allowed = 1
        if doc.doctype in user.can_cancel:
            allowed = 1
        if allowed == 0:
            for itm in doc.items:
                it_doc = frappe.get_doc("Item", itm.item_code)
                bom_tmp = get_bom_template_from_item(it_doc)
                if bom_tmp:
                    for bte in bom_tmp:
                        frappe.msgprint(f"{frappe.get_desk_link(it_doc.doctype, it_doc.name)} "
                            f"already has {frappe.get_desk_link('BOM Template RIGPL', bte)}.\
                            So make Stock Entries via Job Card")
                    frappe.throw(f"Not Allowed to Stock Entries for \
                        {frappe.get_desk_link(it_doc.doctype, it_doc.name)}")


def update_valuation_rate(ste):
    """
    Updates the Valuation Rate for an Item
    """
    for itm in ste.items:
        itd = frappe.get_doc("Item", itm.item_code)
        if itd.made_to_order != 1:
            # Check if its purchase item or manufacture item if manufactured item them Valuation
            # Rate from Item Doc and if its a purchase item then as per fifo rate in that warehouse
            if itd.include_item_in_manufacturing == 1:
                itm.basic_rate = itd.valuation_rate
                itm.valuation_rate = itd.valuation_rate
                itm.amount = itd.valuation_rate * itm.qty
                itm.basic_amount = itd.valuation_rate * itm.qty
                if itd.valuation_rate > 0:
                    itm.allow_zero_valuation_rate = 0
                else:
                    itm.allow_zero_valuation_rate = 1
            else:
                # Generally the system takes the incoming valuation rate automatically
                pass
        else:
            itm.basic_rate = 1
            itm.valuation_rate = 1
            itm.basic_amount = itm.qty
            itm.amount = itm.qty
            itm.allow_zero_valuation_rate = 0
    StockEntry.set_total_incoming_outgoing_value(ste)


def check_stock_recon(ste):
    """
    Check if the Item has a Stock Reconciliation after the date and time of posting or NOT.
    If there is a Stock Reconciliation then the submission would not be allowed for stock entry
    """
    sr_list = []
    sr_row = frappe._dict({})
    def_stk_adj_acc = frappe.get_value("Company", ste.company, "stock_adjustment_account")
    for row in ste.items:
        row.expense_account = def_stk_adj_acc
        ste_dt_time = dt.datetime.combine(getdate(ste.posting_date), get_time(ste.posting_time))
        query = f"""SELECT name, voucher_no, CONCAT(posting_date, ' ', posting_time) as ptime
        FROM `tabStock Ledger Entry` WHERE item_code = '{row.item_code}' AND
        warehouse = '{row.s_warehouse}' AND voucher_type = 'Stock Reconciliation'
        AND CONCAT(posting_date, ' ', posting_time) >= '{ste_dt_time}' LIMIT 1"""
        sr_swh = frappe.db.sql(query, as_dict=1)
        if sr_swh:
            sr_row["idx"] = row.idx
            sr_row["ic"] = row.item_code
            sr_row["wh"] = row.s_warehouse
            sr_row["srn"] = sr_swh[0].voucher_no
            sr_row["ptime"] = sr_swh[0].ptime
            sr_list.append(sr_row.copy())
        # Check the Stock Reconciliation for Target Warehouse as well
        query = f"""SELECT name, voucher_no, CONCAT(posting_date, ' ', posting_time) as ptime
        FROM `tabStock Ledger Entry` WHERE item_code = '{row.item_code}'
        AND warehouse = '{row.t_warehouse}' AND voucher_type = 'Stock Reconciliation'
        AND CONCAT(posting_date, ' ', posting_time) >= '{ste_dt_time}' LIMIT 1"""
        sr_twh = frappe.db.sql(query, as_dict=1)
        if sr_twh:
            sr_row["idx"] = row.idx
            sr_row["ic"] = row.item_code
            sr_row["wh"] = row.t_warehouse
            sr_row["srn"] = sr_twh[0].voucher_no
            sr_row["ptime"] = sr_twh[0].ptime
            sr_list.append(sr_row.copy())
    if sr_list:
        for srn in sr_list:
            frappe.msgprint(f"In Row# {srn.idx} and Item: {srn.ic} for {srn.wh} there is "
                f"Stock Reconciliation {srn.srn} at {srn.ptime}")
        frappe.throw("Cannot Proceed")


def update_ste_date(ste):
    """
    If STE linked to PO then status of Stock Entry cannot be different from PO
    along with posting date and time
    """
    if ste.purchase_order:
        podoc = frappe.get_doc("Purchase Order", ste.purchase_order)
        ste.posting_date = podoc.transaction_date
        ste.posting_time = '23:59:59'
    elif ste.purchase_receipt_no:
        grn = frappe.get_doc("Purchase Receipt", ste.purchase_receipt_no)
        ste.posting_date = grn.posting_date
        ste.posting_time = grn.posting_time
    elif ste.process_job_card:
        jcd = frappe.get_doc("Process Job Card RIGPL", ste.process_job_card)
        ste.posting_date = jcd.posting_date
        ste.posting_time = jcd.posting_time
