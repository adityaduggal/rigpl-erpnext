# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from rigpl_erpnext.utils.sales_utils import *


def validate(doc, method):
    update_fields(doc)
    check_dynamic_link(parenttype="Address", parent=doc.customer_address, link_doctype="Customer",
                       link_name=doc.customer)
    check_dynamic_link(parenttype="Address", parent=doc.shipping_address_name,
                       link_doctype="Customer", link_name=doc.customer)
    check_dynamic_link(parenttype="Contact", parent=doc.contact_person, link_doctype="Customer", link_name=doc.customer)
    check_gst_rules(doc, doc.customer_address, doc.taxes_and_charges)
    check_delivery_note_rule(doc, method)
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


def check_delivery_note_rule(doc, method):
    dn_dict = frappe._dict()
    list_of_dn_dict = []

    for d in doc.items:
        # Stock Items without DN would need Update Stock Check
        if d.delivery_note is None:
            item_doc = frappe.get_doc('Item', d.item_code)
            if item_doc.is_stock_item == 1 and doc.update_stock != 1:
                frappe.throw(("Item Code {0} in Row # {1} is Stock Item without any DN so please check "
                              "Update Stock Button").format(d.item_code, d.idx))

        if d.dn_detail not in list_of_dn_dict and d.delivery_note is not None:
            dn_dict['dn'] = d.delivery_note
            dn_dict['dn_detail'] = d.dn_detail
            dn_dict['item_code'] = d.item_code
            list_of_dn_dict.append(dn_dict.copy())
        # With SO DN is mandatory
        if d.sales_order is not None and d.delivery_note is None:
            # Rule no.5 in the above description for disallow SO=>SI no skipping DN
            frappe.throw(("""Error in Row# {0} has SO# {1} but there is no DN. 
            Hence making of Invoice is DENIED""").format(d.idx, d.sales_order))
        # With DN SO is mandatory
        if d.delivery_note is not None and d.sales_order is None:
            frappe.throw(("""Error in Row# {0} has DN# {1} but there is no SO. 
            Hence making of Invoice is DENIED""").format(d.idx, d.delivery_note))
        # For DN items quantities should be same
        if d.delivery_note is not None:
            dn_qty = frappe.db.get_value('Delivery Note Item', d.dn_detail, 'qty')
            if dn_qty != d.qty:
                frappe.throw("Invoice Qty should be equal to DN quantity of {0} at Row # {1}".format(dn_qty, d.idx))
    if list_of_dn_dict:
        unique_dn = {v['dn']: v for v in list_of_dn_dict}.values()
        for dn in unique_dn:
            dn_doc = frappe.get_doc('Delivery Note', dn.dn)
            for d in dn_doc.items:
                if not any(x['dn_detail'] == d.name for x in list_of_dn_dict):
                    frappe.throw(("Item No: {0} with Item Code: {1} in DN# {2} is not mentioned in "
                                  "SI# {3}").format(d.idx, d.item_code, dn_doc.name, doc.name))


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
    exists = frappe.db.sql(query)
    if exists:
        return exists


def is_tracked_transporter(doc, method):
    fedex = frappe.get_value("Transporters", doc.transporters, "fedex_credentials")
    fedex_track = frappe.get_value("Transporters", doc.transporters, "fedex_tracking_only")
    shipway = frappe.get_value("Transporters", doc.transporters, "track_on_shipway")
    if fedex == 1 or shipway == 1 or fedex_track == 1:
        ttrans = 1
    else:
        ttrans = 0
    return ttrans


def new_brc_tracking(doc, method):
    # If SI is from Cancelled DOC then UPDATE the details of same in BRC
    stct_doc = frappe.get_doc("Sales Taxes and Charges Template", doc.taxes_and_charges)
    add_doc = frappe.get_doc("Address", doc.shipping_address_name)
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
