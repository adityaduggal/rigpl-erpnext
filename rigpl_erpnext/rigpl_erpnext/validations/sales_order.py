# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from frappe.utils import nowdate
from rigpl_erpnext.utils.sales_utils import *
from rohit_common.utils.rohit_common_utils import check_dynamic_link
from rigpl_erpnext.utils.stock_utils import make_sales_job_work_ste, cancel_delete_ste_from_name


def validate(doc, method):
    validate_address_google_update(doc.customer_address)
    validate_address_google_update(doc.shipping_address_name)
    check_validated_gstin(doc.customer_address)
    check_validated_gstin(doc.shipping_address_name)
    dead_stock_order_booking(doc)
    check_dynamic_link(parenttype="Address", parent=doc.customer_address,
                       link_doctype="Customer", link_name=doc.customer)
    check_dynamic_link(parenttype="Address", parent=doc.shipping_address_name,
                       link_doctype="Customer", link_name=doc.customer)
    check_dynamic_link(parenttype="Contact", parent=doc.contact_person,
                       link_doctype="Customer", link_name=doc.customer)
    cust_doc = frappe.get_doc("Customer", doc.customer)
    if cust_doc.customer_primary_contact is None:
        frappe.throw("Cannot Book Sales Order since Customer " + cust_doc.name +
                     " does not have a Primary Contact Defined")

    if cust_doc.customer_primary_address is None:
        frappe.throw("Cannot Book Sales Order since Customer " + cust_doc.name +
                     " does not have a Primary Address Defined")

    if cust_doc.sales_team is None:
        frappe.throw("Cannot Book Sales Order since Customer " + cust_doc.name +
                     " does not have a Sales Team Defined")
    update_fields(doc)
    check_gst_rules(doc, doc.customer_address, doc.taxes_and_charges)
    check_taxes_integrity(doc)
    check_price_list(doc)


def check_price_list(doc):
    for it in doc.items:
        if it.price_list:
            check_get_pl_rate(doc, it)
        else:
            it.price_list = doc.selling_price_list
            check_get_pl_rate(doc, it)


def update_fields(doc):
    cust_doc = frappe.get_doc("Customer", doc.customer)
    if cust_doc.follow_strict_po_rules == 1:
        doc.follow_strict_po_rules = 1
    # Adding the Sales Team data from Customer to the Sales Team of Sales Order.
    # This is how you add data in Child table.
    doc.sales_team = []
    steam_dict = {}
    for d in cust_doc.sales_team:
        steam_dict["sales_person"] = d.sales_person
        steam_dict["allocated_percentage"] = d.allocated_percentage
        doc.append("sales_team", steam_dict.copy())
    doc.shipping_address_title = frappe.get_value("Address",
                                                  doc.shipping_address_name, "address_title")
    if doc.transaction_date < nowdate():
        doc.transaction_date = nowdate()
    if doc.delivery_date < doc.transaction_date:
        doc.delivery_date = doc.transaction_date
    for d in doc.items:
        if d.delivery_date < doc.transaction_date:
            d.delivery_date = doc.transaction_date

    letter_head_tax = frappe.db.get_value("Sales Taxes and Charges Template",
                                          doc.taxes_and_charges, "letter_head")
    doc.letter_head = letter_head_tax

    for items in doc.items:
        get_hsn_code(items)


def on_submit(so, method):
    make_sales_job_work_ste(so_no=so.name)
    so.submitted_by = so.modified_by
    if so.track_trial == 1:
        no_of_team = 0

        for s_team in so.get("sales_team"):
            no_of_team = len(so.get("sales_team"))

        if no_of_team != 1:
            frappe.msgprint("Please enter exactly one Sales Person who is responsible for carrying out the Trials",
                            raise_exception=1)

        for sod in so.get("items"):
            tt = frappe.new_doc("Trial Tracking")
            tt.prevdoc_detail_docname = sod.name
            tt.against_sales_order = so.name
            tt.customer = so.customer
            tt.item_code = sod.item_code
            tt.qty = sod.qty
            tt.description = sod.description
            tt.base_rate = sod.base_rate
            tt.trial_owner = s_team.sales_person
            tt.status = "In Production"
            tt.insert()
            query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
            name = frappe.db.sql(query, as_list=1)
            frappe.msgprint('{0}{1}'.format("Created New Trial Tracking Number: ", name[0][0]))


def on_cancel(so, method):
    existing_ste = frappe.db.sql("""SELECT name FROM `tabStock Entry` WHERE docstatus=1 
    AND sales_order='%s'"""% so.name, as_dict=1)
    if existing_ste:
        for ste in existing_ste:
            cancel_delete_ste_from_name(ste.name, trash_can=0)
    if so.track_trial == 1:
        for sod in so.get("items"):
            query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
            name = frappe.db.sql(query, as_list=1)
            if name:
                frappe.delete_doc("Trial Tracking", name[0])
                frappe.msgprint('{0}{1}'.format("Deleted Trial Tracking No: ", name[0][0]))
