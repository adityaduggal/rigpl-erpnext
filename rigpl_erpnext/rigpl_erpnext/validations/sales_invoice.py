#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from rigpl_erpnext.utils.sales_utils import *


def validate(doc, method):
    update_fields(doc)
    check_gst_rules(doc, doc.customer_address, doc.taxes_and_charges)
    validate_price_list(doc, method)
    check_strict_po_rules(doc)
    copy_address_and_check(doc)


def on_submit(doc, method):
    create_new_carrier_track(doc, method)
    new_brc_tracking(doc, method)
    update_shipment_booking(doc, method)
    user = frappe.session.user
    query = """SELECT role from `tabUserRole` where parent = '%s' """ % user
    roles = frappe.db.sql(query, as_list=1)

    for d in doc.items:
        if d.sales_order is None and d.delivery_note is None and doc.ignore_pricing_rule == 1:
            is_stock_item = frappe.db.get_value('Item', d.item_code, 'is_stock_item')
            if is_stock_item == 1:
                if any("System Manager" in s for s in roles):
                    pass
                else:
                    frappe.throw("You are not Authorised to Submit this Transaction ask a System Manager")
        if d.sales_order is not None:
            so = frappe.get_doc("Sales Order", d.sales_order)
            if so.track_trial == 1:
                dnd = frappe.get_doc("Delivery Note Item", d.dn_detail)
                sod = dnd.so_detail
                query = """SELECT tt.name FROM `tabTrial Tracking` tt WHERE tt.prevdoc_detail_docname = '%s' """ % sod
                name = frappe.db.sql(query, as_list=1)
                if name:
                    tt = frappe.get_doc("Trial Tracking", name[0][0])
                    frappe.db.set(tt, 'invoice_no', doc.name)


def on_cancel(doc, method):
    # Get Carrier Tracking
    ctrack = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` WHERE document = 'Sales Invoice' 
    AND document_name = '%s'""" % (doc.name), as_list=1)
    if ctrack:
        ctrack_doc = frappe.get_doc("Carrier Tracking", ctrack[0][0])
        frappe.db.set_value("Carrier Tracking", ctrack[0][0], "document_name", "")
        frappe.db.set_value("Carrier Tracking", ctrack[0][0], "reference_document_name", doc.name)
        frappe.db.set_value("Carrier Tracking", ctrack[0][0], "route", "")
        frappe.db.set_value("Carrier Tracking", ctrack[0][0], "published", 0)

    for d in doc.items:
        if d.sales_order is not None:
            so = frappe.get_doc("Sales Order", d.sales_order)
            if so.track_trial == 1:
                dnd = frappe.get_doc("Delivery Note Item", d.dn_detail)
                sod = dnd.so_detail
                query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod
                name = frappe.db.sql(query, as_list=1)
                if name:
                    tt = frappe.get_doc("Trial Tracking", name[0][0])
                    frappe.db.set(tt, 'invoice_no', None)


def validate_price_list(doc, method):
    for d in doc.items:
        if d.so_detail:
            sod_doc = frappe.get_doc("Sales Order Item", d.so_detail)
            d.price_list = sod_doc.price_list
        else:
            if d.price_list:
                get_pl_rate(doc, d.price_list, d)
            else:
                d.price_list = doc.selling_price_list
                get_pl_rate(doc, d.price_list, d)


def get_pl_rate(doc, price_list, row):
    pl_doc = frappe.get_doc("Price List", row.price_list)
    it_doc = frappe.get_doc("Item", row.item_code)
    if pl_doc.disable_so == 1 and it_doc.is_stock_item == 1:
        frappe.throw("Sales Invoices for {} are Blocked without prior Sales Order".format(row.price_list))
    else:
        item_price = frappe.db.sql("""SELECT price_list_rate, currency FROM `tabItem Price` WHERE price_list = '%s' 
        AND selling = 1 AND item_code = '%s'""" % (row.price_list, row.item_code), as_list=1)
        if item_price:
            if row.price_list_rate != item_price[0][0] and doc.currency == item_price[0][1]:
                frappe.throw("Item: {} in Row# {} does not match with Price List Rate of {}. Reload the Item".format(
                    row.item_code, row.idx, item_price[0][0]))


def update_fields(doc):
    c_form_tax = frappe.db.get_value("Sales Taxes and Charges Template", doc.taxes_and_charges, "c_form_applicable")
    letter_head_tax = frappe.db.get_value("Sales Taxes and Charges Template", doc.taxes_and_charges, "letter_head")

    doc.c_form_applicable = c_form_tax
    doc.letter_head = letter_head_tax

    ctrack = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` WHERE document = 'Sales Invoice' 
    AND (document_name = '%s' OR reference_document_name = '%s')""" % (doc.name, doc.amended_from), as_list=1)

    if ctrack:
        doc.transporters = frappe.db.get_value("Carrier Tracking", ctrack[0][0], "carrier_name")
        doc.lr_no = frappe.db.get_value("Carrier Tracking", ctrack[0][0], "awb_number")
    elif frappe.db.get_value("Transporters", doc.transporters, "fedex_credentials") == 1:
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
                    route = exist_track.name.lower()
                    frappe.db.set_value("Carrier Tracking", exist_track.name, "published", 1)
                    frappe.db.set_value("Carrier Tracking", exist_track.name, "document_name", doc.name)
                    frappe.db.set_value("Carrier Tracking", exist_track.name, "reference_document_name", "")
                    frappe.db.set_value("Carrier Tracking", exist_track.name, "route", route)
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
    # track.shipment_package_details = [{"shipment_package":"PKG00001", "package_weight":1, "weight_uom":"Kg"}]
    track.flags.ignore_permissions = True
    track.insert()
    frappe.msgprint("Created New {0}".format(frappe.get_desk_link('Carrier Tracking', track.name)))


def check_existing_track(doctype, docname):
    query = """SELECT name FROM `tabCarrier Tracking` WHERE document = '%s' 
    AND (document_name = '%s' OR reference_document_name = '%s') AND docstatus != 2""" % (doctype, docname, docname)
    exists = frappe.db.sql(query, as_list=1)
    if exists:
        return exists


def is_tracked_transporter(doc, method):
    tpt_doc = frappe.get_doc("Transporters", doc.transporters)
    if tpt_doc.fedex_credentials == 1 or tpt_doc.fedex_tracking_only == 1 or tpt_doc.track_on_shipway == 1 or \
            tpt_doc.dtdc_credentials == 1 or tpt_doc.dtdc_tracking_only == 1:
        ttrans = 1
    else:
        ttrans = 0
    return ttrans


def new_brc_tracking(doc, method):
    # If SI is from Cancelled DOC then UPDATE the details of same in BRC
    stct_doc = frappe.get_doc("Sales Taxes and Charges Template", doc.taxes_and_charges)
    add_doc = frappe.get_doc("Address", doc.shipping_address_name)
    if stct_doc.is_sample == 1:
        return
    if stct_doc.is_export == 1 and add_doc.country != "India":
        if doc.amended_from:
            is_exist = frappe.db.sql("""SELECT name FROM `tabBRC MEIS Tracking` 
            WHERE reference_name = '%s'""" % doc.amended_from, as_list=1)
            if not is_exist and stct_doc.is_sample != 1:
                create_new_brc_tracking(doc, method)
            else:
                exist_brc = frappe.get_doc("BRC MEIS Tracking", is_exist[0][0])
                exist_brc.reference_name = doc.name
                exist_brc.flags.ignore_permissions = True
                exist_brc.save()
                frappe.msgprint("Updated {0}".format(frappe.get_desk_link('BRC MEIS Tracking', exist_brc.name)))
        else:
            is_exist = frappe.db.sql("""SELECT name FROM `tabBRC MEIS Tracking` 
            WHERE reference_name = '%s'""" % doc.name, as_list=1)
            if not is_exist and stct_doc.is_sample != 1:
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
        bk_ship = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` WHERE docstatus != 2 
        AND document = 'Sales Invoice' AND document_name = '%s'""" % doc.amended_from, as_list=1)
        for bks in bk_ship:
            frappe.db.set_value("Carrier Tracking", bks[0], "document_name", doc.name)
