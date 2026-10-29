# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import datetime as dt
from frappe.utils import flt, getdate, get_time
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from ...manufacturing_rigpl.utils.manufacturing_utils import get_bom_template_from_item
from ...utils.item_attribute_utils import get_attribute_rows
from ..scheduled_tasks.item_valuation_rate import get_cut_pcs_factor


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
    Updates the Valuation Rate for an Item some basic things to know
    - If Source Warehouse is Not ther then Get the Valuation Rate from Item Master
    - A cut piece of a rod consumed in the same entry gets its rate from that rod (#155)
    """
    item_codes = list({itm.item_code for itm in ste.items})
    items = {
        d.name: d
        for d in frappe.get_all(
            "Item", filters={"name": ["in", item_codes]},
            fields=["name", "variant_of", "is_purchase_item", "valuation_rate"],
        )
    }
    lengths = get_lengths(item_codes)
    for itm in ste.items:
        if not itm.s_warehouse:
            vrate = get_cut_piece_rate(itm, ste.items, items, lengths)
            if vrate is None:
                vrate = flt(items[itm.item_code].valuation_rate)
            itm.basic_rate = vrate
            itm.valuation_rate = vrate
            itm.amount = vrate * itm.qty
            itm.basic_amount = vrate * itm.qty
            if vrate > 0:
                itm.allow_zero_valuation_rate = 0
            else:
                itm.allow_zero_valuation_rate = 1
    StockEntry.set_total_incoming_outgoing_value(ste)


def get_lengths(item_codes):
    """
    Returns {item_code: l1_mm} for the items which have the l1_mm attribute
    """
    lengths = {}
    for item_code, rows in get_attribute_rows(item_codes).items():
        for row in rows:
            if row.attribute == "l1_mm" and flt(row.attribute_value) > 0:
                lengths[item_code] = flt(row.attribute_value)
    return lengths


def get_cut_piece_rate(row, ste_rows, items, lengths):
    """
    Returns the rate of a purchase item cut from the longest rod of the same template that is
    consumed in the same entry, as rod rate x length ratio x cut pieces factor. Returns None
    if no such rod is consumed.
    """
    itd = items[row.item_code]
    cut_len = lengths.get(row.item_code)
    if not itd.is_purchase_item or not itd.variant_of or not cut_len:
        return None
    rods = [
        d for d in ste_rows
        if d.s_warehouse and not d.t_warehouse and flt(d.basic_rate) > 0
        and items[d.item_code].variant_of == itd.variant_of
        and lengths.get(d.item_code, 0) >= cut_len
    ]
    if not rods:
        return None
    rod = max(rods, key=lambda d: lengths[d.item_code])
    rod_len = lengths[rod.item_code]
    return flt(rod.basic_rate) * cut_len / rod_len * get_cut_pcs_factor(cut_len, rod_len)


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
