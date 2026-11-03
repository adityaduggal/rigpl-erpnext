#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import re
import frappe
from rigpl_erpnext.rigpl_erpnext.shipping.accounts import BOOKING, NONE
from rigpl_erpnext.rigpl_erpnext.shipping.registry import transporter_api
from rigpl_erpnext.utils.sales_utils import check_gst_rules, check_strict_po_rules, copy_address_and_check, \
    copy_so_price_lists, get_item_price_rows, get_linked_so_data



def validate(doc, method):
    update_fields(doc)
    check_gst_rules(doc, doc.customer_address, doc.taxes_and_charges)
    validate_price_list(doc, method)
    so_data = get_linked_so_data(doc)
    check_strict_po_rules(doc, so_data)
    copy_address_and_check(doc, so_data)


def on_submit(doc, method):
    check_untracked_stock_items(doc)
    create_new_carrier_track(doc, method)
    new_brc_tracking(doc, method)
    update_shipment_booking(doc, method)
    set_trial_invoice(doc, doc.name)


def on_cancel(doc, method):
    ctrack = frappe.db.get_value("Carrier Tracking", {"document": "Sales Invoice", "document_name": doc.name})
    if ctrack:
        frappe.db.set_value("Carrier Tracking", ctrack, {"document_name": "", "reference_document_name": doc.name,
            "route": "", "published": 0})
    set_trial_invoice(doc, None)


def check_untracked_stock_items(doc):
    """Only a System Manager can submit stock items without a Sales Order and Delivery Note when the
    pricing rule is ignored"""
    if doc.ignore_pricing_rule != 1:
        return
    item_codes = {d.item_code for d in doc.items if not d.sales_order and not d.delivery_note}
    if not item_codes:
        return
    if frappe.get_all("Item", filters={"name": ("in", list(item_codes)), "is_stock_item": 1}, limit=1) and \
            "System Manager" not in frappe.get_roles():
        frappe.throw("You are not Authorised to Submit this Transaction ask a System Manager")


def set_trial_invoice(doc, invoice_no):
    """Sets invoice_no in the Trial Tracking of each row whose Sales Order tracks trials"""
    rows = [d for d in doc.items if d.sales_order]
    if not rows:
        return
    tracked = set(frappe.get_all("Sales Order", filters={"name": ("in", list({d.sales_order for d in rows})),
        "track_trial": 1}, pluck="name"))
    rows = [d for d in rows if d.sales_order in tracked]
    if not rows:
        return
    dn_details = [d.dn_detail for d in rows if d.dn_detail]
    dn_so_details = dict(frappe.get_all("Delivery Note Item", filters={"name": ("in", dn_details)},
        fields=["name", "so_detail"], as_list=1)) if dn_details else {}
    so_details = {dn_so_details.get(d.dn_detail) if d.dn_detail else d.so_detail for d in rows} - {None, ""}
    if not so_details:
        return
    trials = {}
    for tt in frappe.get_all("Trial Tracking", filters={"prevdoc_detail_docname": ("in", list(so_details))},
            fields=["name", "prevdoc_detail_docname"], order_by="name asc"):
        trials.setdefault(tt.prevdoc_detail_docname, tt.name)
    if trials:
        frappe.db.set_value("Trial Tracking", {"name": ("in", list(trials.values()))}, "invoice_no", invoice_no)


def validate_price_list(doc, method):
    copy_so_price_lists(doc)
    rows = [d for d in doc.items if not d.so_detail]
    for d in rows:
        if not d.price_list:
            d.price_list = doc.selling_price_list
    get_pl_rates(doc, rows)


def get_pl_rates(doc, rows):
    """Stock items need a Sales Order for a Price List with disable_so, and the rate must match the Price List"""
    if not rows:
        return
    price_lists = list({row.price_list for row in rows if row.price_list})
    disabled = set(frappe.get_all("Price List", filters={"name": ("in", price_lists), "disable_so": 1},
        pluck="name")) if price_lists else set()
    stock_items = set(frappe.get_all("Item", filters={"name": ("in", list({row.item_code for row in rows})),
        "is_stock_item": 1}, pluck="name")) if disabled else set()
    prices = get_item_price_rows([(row.item_code, row.price_list) for row in rows], selling_only=True)
    for row in rows:
        if row.price_list in disabled and row.item_code in stock_items:
            frappe.throw("Sales Invoices for {} are Blocked without prior Sales Order".format(row.price_list))
        item_price = prices.get((row.item_code, row.price_list))
        if item_price and row.price_list_rate != item_price.price_list_rate and doc.currency == item_price.currency:
            frappe.throw("Item: {} in Row# {} does not match with Price List Rate of {}. Reload the Item".format(
                row.item_code, row.idx, item_price.price_list_rate))


def get_pl_rate(doc, price_list, row):
    get_pl_rates(doc, [row])


def update_fields(doc):
    if doc.taxes_and_charges:
        tax = frappe.get_cached_value("Sales Taxes and Charges Template", doc.taxes_and_charges,
            ["c_form_applicable", "letter_head"], as_dict=True)
    else:
        tax = frappe._dict()
    doc.c_form_applicable = tax.c_form_applicable
    doc.letter_head = tax.letter_head

    ct = frappe.qb.DocType("Carrier Tracking")
    match = ct.document_name == doc.name
    if doc.amended_from:
        match = match | (ct.reference_document_name == doc.amended_from)
    ctrack = frappe.qb.from_(ct).select(ct.carrier_name, ct.awb_number) \
        .where((ct.document == "Sales Invoice") & match).limit(1).run(as_dict=True)

    if ctrack:
        doc.transporters = ctrack[0].carrier_name
        doc.lr_no = ctrack[0].awb_number
    elif doc.transporters and transporter_api(doc.transporters) == ("FedEx", BOOKING):
        doc.lr_no = "NA"
    else:
        doc.lr_no = re.sub('[^A-Za-z0-9]+', '', str(doc.lr_no))


def create_new_carrier_track(doc, method):
    # If SI is from Cancelled Doc then update the Existing Carrier Track
    is_tracked = is_tracked_transporter(doc, method)
    if is_tracked == 1:
        if doc.amended_from:
            existing_track = check_existing_track(doc.doctype, doc.amended_from)
            if existing_track:
                exist_track = frappe.get_doc("Carrier Tracking", existing_track[0][0])
                if exist_track.docstatus == 0:
                    doc.lr_no = exist_track.awb_number
                    exist_track.receiver_name = doc.customer
                    exist_track.document_name = doc.name
                    doc.transporters = exist_track.carrier_name
                    exist_track.reference_document_name = ""
                    exist_track.flags.ignore_permissions = True
                    exist_track.save()
                    frappe.msgprint("Updated {0}".format(frappe.get_desk_link('Carrier Tracking', exist_track.name)))
                elif exist_track.docstatus == 1:
                    frappe.db.set_value("Carrier Tracking", exist_track.name, {"published": 1,
                        "document_name": doc.name, "reference_document_name": "",
                        "route": exist_track.name.lower()})
                else:
                    new_ctrack = frappe.copy_doc(exist_track)
                    new_ctrack.amended_from = exist_track.name
                    new_ctrack.document_name = doc.name
                    new_ctrack.insert(ignore_permissions=True)
                    frappe.msgprint("Added New {0}".format(frappe.get_desk_link('Carrier Tracking', new_ctrack.name)))
            else:
                create_new_ship_track(doc)

        elif check_existing_track(doc.doctype, doc.name) is None:
            # Dont create a new Tracker if already exists
            create_new_ship_track(doc)


def create_new_ship_track(si_doc):
    track = frappe.new_doc("Carrier Tracking")
    track.carrier_name = si_doc.transporters
    track.awb_number = si_doc.lr_no
    track.receiver_document = "Customer"
    track.receiver_name = si_doc.customer
    track.document = "Sales Invoice"
    track.document_name = si_doc.name
    track.flags.ignore_permissions = True
    track.insert()
    frappe.msgprint("Created New {0}".format(frappe.get_desk_link('Carrier Tracking', track.name)))


def check_existing_track(doctype, docname):
    """Returns [[name], ...] of the Carrier Trackings (not cancelled) of the document, or None"""
    ct = frappe.qb.DocType("Carrier Tracking")
    exists = frappe.qb.from_(ct).select(ct.name).where(
        (ct.document == doctype) & ((ct.document_name == docname) | (ct.reference_document_name == docname))
        & (ct.docstatus != 2)).run(as_list=True)
    if exists:
        return exists


def is_tracked_transporter(doc, method):
    return 0 if transporter_api(doc.transporters)[1] == NONE else 1


def new_brc_tracking(doc, method):
    # If SI is from Cancelled DOC then UPDATE the details of same in BRC
    stct = frappe.get_cached_value("Sales Taxes and Charges Template", doc.taxes_and_charges,
        ["is_sample", "is_export"], as_dict=True)
    if stct.is_sample == 1 or stct.is_export != 1:
        return
    if frappe.get_cached_value("Address", doc.shipping_address_name, "country") == "India":
        return
    if doc.amended_from:
        is_exist = frappe.db.get_value("BRC MEIS Tracking", {"reference_name": doc.amended_from})
        if not is_exist:
            create_new_brc_tracking(doc, method)
        else:
            exist_brc = frappe.get_doc("BRC MEIS Tracking", is_exist)
            exist_brc.reference_name = doc.name
            exist_brc.flags.ignore_permissions = True
            exist_brc.save()
            frappe.msgprint("Updated {0}".format(frappe.get_desk_link('BRC MEIS Tracking', exist_brc.name)))
    elif not frappe.db.get_value("BRC MEIS Tracking", {"reference_name": doc.name}):
        create_new_brc_tracking(doc, method)


def create_new_brc_tracking(doc, method):
    brc_doc = frappe.new_doc("BRC MEIS Tracking")
    brc_doc.flags.ignore_permissions = True
    brc_doc.export_or_import = 'Export'
    brc_doc.reference_doctype = doc.doctype
    brc_doc.reference_name = doc.name
    brc_doc.insert()
    frappe.msgprint("Created New {0}".format(frappe.get_desk_link('BRC MEIS Tracking', brc_doc.name)))


def update_shipment_booking(doc, method):
    if doc.amended_from:
        frappe.db.set_value("Carrier Tracking", {"docstatus": ("!=", 2), "document": "Sales Invoice",
            "document_name": doc.amended_from}, "document_name", doc.name)
