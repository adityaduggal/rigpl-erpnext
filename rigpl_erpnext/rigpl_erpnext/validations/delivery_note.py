# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from datetime import datetime as dt
from datetime import date
from frappe.utils import getdate
from ...utils.sales_utils import check_strict_po_rules, copy_address_and_check, validate_made_to_order_items
from ...utils.stock_utils import get_reconciliations_after


def validate(doc, method):
    # Check if the Item has a Stock Reconciliation after the date and time or NOT.
    # if there is a Stock Reconciliation then the Update would FAIL
    # Also check if the items are from Same Price List SO as is the PL mentioned in the DN
    check_draft_dn(doc)
    check_strict_po_rules(doc)
    copy_address_and_check(doc)
    check_price_list(doc, method)
    for dnd in doc.get("items"):
        if not dnd.against_sales_order:
            frappe.throw("Delivery Note {} not against any Sales Order at Row {}".format(doc.name, dnd.idx))
    srs = get_reconciliations_after([(d.item_code, d.warehouse) for d in doc.get("items")],
        doc.posting_date, doc.posting_time)
    for dnd in doc.get("items"):
        sr = srs.get((dnd.item_code, dnd.warehouse))
        if not sr:
            continue
        if sr.posting_date > getdate(doc.posting_date):
            frappe.throw("There is a Reconciliation for Item Code: {0} after "
                         "the posting date".format(dnd.item_code))
        frappe.throw("There is a Reconciliation for Item Code: {0} after the posting time".
                     format(dnd.item_code))


def check_draft_dn(dn_doc):
    if dn_doc.is_new() == 1:
        oth_dn = frappe.db.get_value("Delivery Note", {"docstatus": 0, "customer": dn_doc.customer,
            "name": ("!=", dn_doc.name)})
        if oth_dn:
            frappe.throw(f"{frappe.get_desk_link('Delivery Note', oth_dn)} Already In Draft for "
                         f"{dn_doc.customer} Use that Delivery Note")


def check_price_list(doc, method):
    so_details = [it.so_detail for it in doc.items if it.so_detail]
    if not so_details:
        return
    price_lists = dict(frappe.get_all("Sales Order Item", filters={"name": ("in", so_details)},
        fields=["name", "price_list"], as_list=1))
    for it in doc.items:
        if it.so_detail:
            it.price_list = price_lists.get(it.so_detail)


def on_submit(doc, method):
    validate_made_to_order_items(doc)
    update_trial_status(doc, "Material Ready")


def on_cancel(doc, method):
    make_ste_for_reconciled_items(doc)
    update_trial_status(doc, "In Production")


def update_trial_status(doc, status):
    """Set the status of the Trial Tracking of each row whose Sales Order tracks trials."""
    rows = [d for d in doc.get("items") if d.so_detail and d.against_sales_order]
    if not rows:
        return
    tracked = set(frappe.get_all("Sales Order", filters={"name": ("in", {d.against_sales_order for d in rows}),
        "track_trial": 1}, pluck="name"))
    for dnd in rows:
        if dnd.against_sales_order not in tracked:
            continue
        name = frappe.db.get_value("Trial Tracking", {"prevdoc_detail_docname": dnd.so_detail})
        if not name:
            frappe.throw("No Trial Tracking for Sales Order {} Row {}".format(dnd.against_sales_order,
                dnd.so_detail))
        frappe.db.set_value("Trial Tracking", name, "status", status)
        frappe.msgprint('{0}{1}'.format("Updated Status of Trial No: ", name))


def make_ste_for_reconciled_items(doc):
    ste_list = []
    remarks = f"Stock Entry Due to Cancellation of DN# {doc.name} with Posting Date {doc.posting_date} on {dt.now()}"
    items = {d.name: d for d in frappe.get_all("Item", filters={"name": ("in", {d.item_code for d in doc.items})},
        fields=["name", "is_stock_item", "made_to_order"])}
    srs = get_reconciliations_after([(d.item_code, d.warehouse) for d in doc.items], doc.posting_date,
        doc.posting_time, inclusive=False)
    for d in doc.items:
        itd = items[d.item_code]
        sr = srs.get((d.item_code, d.warehouse))
        if itd.is_stock_item == 1 and itd.made_to_order != 1 and sr:
            remarks += (f"\nFor Row# {d.idx} and Item: {d.item_code} there was "
                f"Stock Reconciliation: {sr.voucher_no}")
            ste_list.append({
                "item_code": d.item_code,
                "t_warehouse": d.warehouse,
                "qty": d.qty,
                "uom": d.uom,
                "stock_uom": d.stock_uom,
                "conversion_factor": d.conversion_factor,
            })
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
