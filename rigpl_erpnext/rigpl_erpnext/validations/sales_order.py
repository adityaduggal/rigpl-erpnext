#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import json
from frappe.utils import nowdate
from ...utils.other_utils import remove_html
from ...utils.sales_utils import *
from rohit_common.utils.rohit_common_utils import check_dynamic_link, check_sales_taxes_integrity
from rohit_common.rohit_common.validations.sales_invoice import check_validated_gstin
from rigpl_erpnext.utils.stock_utils import make_sales_job_work_ste, cancel_delete_ste_from_name
from rigpl_erpnext.utils.accounts_receivable_utils import check_overdue_receivables
from rigpl_erpnext.utils.process_sheet_utils import create_ps_from_so_item


def validate(doc, method):
    validate_item_pack_size(doc, enforce=0)
    validate_item_mov(doc, enforce=0)
    validate_address_google_update(doc.customer_address)
    validate_address_google_update(doc.shipping_address_name)
    add_list = [doc.customer_address, doc.shipping_address_name]
    for add in add_list:
        check_validated_gstin(add, doc)
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
    check_sales_taxes_integrity(doc)
    check_price_list(doc)


def check_price_list(doc):
    """
    Removes HTML from Item Description and Also Adds Price List if not there in Item Table
    1. If Item is a Variant of and not made to order then it should have Price List Rate
    2. Also base net rate cannot be lower than item valuation rate
    """
    for it in doc.items:
        itd = frappe.get_doc("Item", it.item_code)
        it.description = remove_html(it.description)
        if not it.price_list:
            it.price_list = doc.selling_price_list
        if itd.made_to_order != 1 and itd.variant_of:
            it_price = get_item_price(it.item_code, it.price_list)
            if not it_price:
                frappe.throw(f"In Row# {it.idx} for Item: {it.item_code} No Price List Rate "
                    f"for {it.price_list} Create a Price List Rate to Proceed or Remove Item.")
            if it.base_net_rate < itd.valuation_rate:
                frappe.throw(f"In Row# {it.idx} for Item: {it.item_code} Selling Base Price "
                    f"{it.base_net_rate} is Lower than Valuation Rate {itd.valuation_rate}<br>"
                    f"To Proceed Correct the Price.")


def update_fields(doc):
    cust_doc = frappe.get_doc("Customer", doc.customer)
    if cust_doc.follow_strict_po_rules == 1:
        doc.follow_strict_po_rules = 1
    # Adding the Sales Team data from Customer to the Sales Team of Sales Order.
    # This is how you add data in Child table.
    doc.sales_team = []
    steam_dict = {}
    doc.sales_partner = cust_doc.default_sales_partner
    doc.commission_rate = cust_doc.default_commission_rate
    doc.total_commission = doc.commission_rate * doc.base_net_total / 100
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
    validate_item_pack_size(so)
    validate_item_mov(doc)
    cust_doc = frappe.get_doc("Customer", so.customer)
    if so.bypass_credit_check != 1:
        check_overdue_receivables(cust_doc)
    make_sales_job_work_ste(so_no=so.name)
    makes_process_sheet_if_needed(so)
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
    delete_process_sheet(so)
    existing_ste = frappe.db.sql("""SELECT name FROM `tabStock Entry` WHERE docstatus=1
    AND sales_order='%s'"""% so.name, as_dict=1)
    if existing_ste:
        for ste in existing_ste:
            cancel_delete_ste_from_name(ste.name)
    if so.track_trial == 1:
        for sod in so.get("items"):
            query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
            name = frappe.db.sql(query, as_list=1)
            if name:
                frappe.delete_doc("Trial Tracking", name[0], for_reload=True)
                frappe.msgprint('{0}{1}'.format("Deleted Trial Tracking No: ", name[0][0]))


@frappe.whitelist()
def after_submit(ex_dt, ex_dn, new_so_doc):
    """
    Some validations for changes after submission of Sales Order
        1. Disallow changing the Qty for Item
        2. Prices for Item can only be changed by System Manager or Credit Controller or
        Cancel Rights Role
        3. Stopping for Sales Orders only possible for Sys Mgr or Credit Controller or Cancel Rights
        4. Stopping should be disallowed if already there is Process Sheets submitted for Item
        5. Stopping should be disallowed if No DN is being made since ask user to Cancel instead
    """
    edoc = frappe.get_doc(ex_dt, ex_dn)
    ndoc = json.loads(new_so_doc)
    frappe.throw(f"Earlier Status {edoc.status} and New Doc = {ndoc.get('status')} ")



def makes_process_sheet_if_needed(so):
    for it in so.items:
        it_doc = frappe.get_doc("Item", it.item_code)
        if it_doc.made_to_order == 1:
            create_ps_from_so_item(it)


def delete_process_sheet(so):
    for it in so.items:
        it_doc = frappe.get_doc("Item", it.item_code)
        if it_doc.made_to_order == 1:
            ps_list = frappe.db.sql("""SELECT name FROM `tabProcess Sheet` WHERE docstatus = 0
            AND sales_order_item = '%s' AND sales_order = '%s'""" % (it.name, so.name), as_dict=1)
            if ps_list:
                for ps in ps_list:
                    frappe.delete_doc("Process Sheet", ps.name, for_reload=True)

