#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re
import frappe
import datetime
from frappe.query_builder.functions import Count, Min, Sum
from frappe.utils import add_days, add_months, flt, getdate, today
from pypika.terms import Tuple
from .item_attribute_utils import chunks
from .other_utils import get_base_doc, round_up, auto_round_up, compute_lcm
from .stock_utils import get_qty_available_to_sell
from rohit_common.utils.rohit_common_utils import replace_java_chars


def validate_item_pack_size(so_doc, enforce=1):
    """
    Validation for Pack Size of Items while booking orders basically it would suggest the
    quantity in multiple of Pack Sizes so if Pack Size is 20 then only booking qty would be
    multiples of 20. Check pack size for only Items Not made to order and also should be variant
    of a template
    """
    user_roles = frappe.get_roles(frappe.session.user)
    itm_pkg_lst = []
    cr_cont = frappe.get_value("Accounts Settings", "Accounts Settings", "credit_controller")
    if ("System Manager" or cr_cont) in user_roles:
        enforce = 0
    for itm in so_doc.items:
        it_doc = frappe.get_doc("Item", itm.item_code)
        if it_doc.pack_size <= 0:
            pk_sz = 1
        else:
            pk_sz = it_doc.pack_size
        if it_doc.made_to_order != 1 and it_doc.variant_of:
            if itm.qty % pk_sz != 0:
                sug_qty = round_up(itm.qty, pk_sz)
                pack_message = f"For Row# {itm.idx} and Item Code: {itm.item_code} Pack Size = \
                {pk_sz} but you are trying for Qty= {itm.qty} which is not as per Pack Size <br> \
                Suggested Qty for Pack Size = {sug_qty}"
                if enforce == 1:
                    pack_message += "<br>Validation Failed ask System Manager to \
                        bypass or Change Qty to Suggested Qty"
                itm_pkg_lst.append(pack_message)
    if itm_pkg_lst:
        frappe.msgprint(itm_pkg_lst, as_table=1, raise_exception=enforce)


def validate_item_mov(so_doc, enforce=1):
    """
    Validation for Minimum Order Value (MOV) is based on the following rules:
        1. It checks MoV only if Item is not Made to Order Item
        2. It would only enforce if enforce = 1 with enforce it would send error.
        3. If item is in stock then it would allow booking orders for below MoV value
        4. If item is not in stock and needs production then MoV is to be enforced
        5. Only check MoV for Items which are Variant of Some Template
    """
    user_roles = frappe.get_roles(frappe.session.user)
    itm_mov_lst = []
    cr_cont = frappe.get_value("Accounts Settings", "Accounts Settings", "credit_controller")
    if ("System Manager" or cr_cont) in user_roles:
        enforce = 0
    for itm in so_doc.items:
        it_doc = frappe.get_doc("Item", itm.item_code)
        if it_doc.pack_size <= 0:
            pk_sz = 1
        else:
            pk_sz = it_doc.pack_size
        if it_doc.made_to_order != 1 and it_doc.variant_of:
            # Don't check MOV for Made to Order Items or Items which are not Part of templates
            qty_avail = get_qty_available_to_sell(it_doc)
            if itm.qty > qty_avail:
                if itm.base_net_amount < it_doc.selling_mov:
                    if itm.base_net_rate > 0:
                        sug_qty = round_up(it_doc.selling_mov / itm.base_net_rate, pk_sz) - pk_sz
                    else:
                        sug_qty = round_up(it_doc.selling_mov / 1, pk_sz) - pk_sz
                    mov_message = f"For Row# {itm.idx} and Item: {itm.item_code} Suggested Qty \
                        for SO = {sug_qty} but SO Qty = {itm.qty} But Qty Available for Sales = \
                        {qty_avail}.<br>Since the Item has MoV= {it_doc.selling_mov} and \
                        Pack Size = {it_doc.pack_size}"
                    if enforce == 1:
                        mov_message += "<br>Validation Failed ask System Manager to \
                        bypass or Change Qty to Suggested Qty"
                    itm_mov_lst.append(mov_message)
    if itm_mov_lst:
        frappe.msgprint(itm_mov_lst, as_table=1, raise_exception=enforce)



def get_contact_child_rows(child_doctype, field, contacts):
    """
    Returns {contact: [rows with field]} of a Contact child table (Contact Email, Contact Phone)
    """
    tab = frappe.qb.DocType(child_doctype)
    rows_by_contact = {}
    for chunk in chunks(contacts):
        for row in (
            frappe.qb.from_(tab)
            .select(tab.parent, tab[field])
            .where((tab.parenttype == "Contact") & tab.parent.isin(chunk))
            .orderby(tab.parent)
            .orderby(tab.idx)
            .run(as_dict=True)
        ):
            rows_by_contact.setdefault(row.pop("parent"), []).append(row)
    return rows_by_contact


def get_contact_emails(contacts):
    return get_contact_child_rows("Contact Email", "email_id", contacts)


def get_contact_phones(contacts):
    return get_contact_child_rows("Contact Phone", "phone", contacts)


def get_email_from_contact(contact_name):
    if not contact_name:
        return frappe._dict({})
    return get_contact_emails([contact_name]).get(contact_name, [])


def get_phone_from_contact(contact_name):
    if not contact_name:
        return frappe._dict({})
    return get_contact_phones([contact_name]).get(contact_name, [])


def get_link_contacts(link_doctype, link_names):
    """
    Returns {link_name: [Contact rows]} for the Contacts linked to the documents
    """
    con = frappe.qb.DocType("Contact")
    dl = frappe.qb.DocType("Dynamic Link")
    contacts = {}
    for chunk in chunks(link_names):
        for row in (
            frappe.qb.from_(dl)
            .join(con).on(con.name == dl.parent)
            .select(dl.link_name, con.name)
            .where((dl.parenttype == "Contact") & (dl.link_doctype == link_doctype))
            .where(dl.link_name.isin(chunk))
            .orderby(con.name)
            .run(as_dict=True)
        ):
            contacts.setdefault(row.pop("link_name"), []).append(row)
    return contacts


def get_contacts(name, type):
    return get_link_contacts(type, [name]).get(name, [])


def get_sales_comms(refs, frm_date=None, to_date=None):
    """
    Returns {(reference_doctype, reference_name): [Sales Related Communications, latest first]}.
    communication_date is a Datetime, so to_date takes the full day.
    """
    comm = frappe.qb.DocType("Communication")
    comms = {}
    for chunk in chunks(refs):
        query = (
            frappe.qb.from_(comm)
            .select(
                comm.reference_doctype, comm.reference_name, comm.name, comm.communication_date,
                comm.communication_medium, comm.content, comm.next_action_date, comm.owner,
            )
            .where(comm.communication_subtype == "Sales Related")
            .where(Tuple(comm.reference_doctype, comm.reference_name).isin(
                [Tuple(*ref) for ref in chunk]))
            .orderby(comm.communication_date, order=frappe.qb.desc)
        )
        if frm_date:
            query = query.where(comm.communication_date >= getdate(frm_date))
        if to_date:
            query = query.where(comm.communication_date < add_days(getdate(to_date), 1))
        for row in query.run(as_dict=True):
            key = (row.pop("reference_doctype"), row.pop("reference_name"))
            comms.setdefault(key, []).append(row)
    return comms


def get_sales_comms_for_customers(customers, frm_date=None, to_date=None):
    """
    Returns {customer: [Communications]} with the Customer's own Communications first, then the
    ones of all its linked Contacts, latest first. Each row has contacts = the number of rows of
    the customer.
    """
    contacts = get_link_contacts("Customer", customers)
    refs = {cust: [("Contact", con.name) for con in contacts.get(cust, [])] for cust in customers}
    comms = get_sales_comms([("Customer", cust) for cust in refs]
        + [ref for cust_refs in refs.values() for ref in cust_refs], frm_date, to_date)
    result = {}
    for cust, cust_refs in refs.items():
        contact_rows = sorted((row for ref in cust_refs for row in comms.get(ref, [])),
            key=lambda row: row.communication_date or datetime.datetime.min, reverse=True)
        rows = [frappe._dict(row) for row in comms.get(("Customer", cust), []) + contact_rows]
        for row in rows:
            row["contacts"] = len(rows)
        result[cust] = rows
    return result


def get_lead_comm_counts(leads):
    """
    Returns {lead: number of all its Communications}
    """
    comm = frappe.qb.DocType("Communication")
    counts = {}
    for chunk in chunks(leads):
        counts.update(dict(
            frappe.qb.from_(comm)
            .select(comm.reference_name, Count(comm.name))
            .where((comm.reference_doctype == "Lead") & comm.reference_name.isin(chunk))
            .groupby(comm.reference_name)
            .run()
        ))
    return counts


def get_sales_comms_for_leads(leads, frm_date=None, to_date=None):
    """
    Returns {lead: [Communications]}. Each row has contacts = the number of all the
    Communications of the lead.
    """
    comms = get_sales_comms([("Lead", lead) for lead in leads], frm_date, to_date)
    counts = get_lead_comm_counts(leads)
    result = {}
    for lead in leads:
        rows = comms.get(("Lead", lead), [])
        for row in rows:
            row["contacts"] = counts.get(lead, 0)
        result[lead] = rows
    return result


def get_sales_comm_for_cust(cust_name, frm_date=None, to_date=None):
    return get_sales_comms_for_customers([cust_name], frm_date, to_date)[cust_name]


def get_sales_comm_for_lead(lead_name, frm_date=None, to_date=None):
    return get_sales_comms_for_leads([lead_name], frm_date, to_date)[lead_name]


def get_pending_so_qty_from_soitem(so_item):
    so = frappe.qb.DocType("Sales Order")
    sod = frappe.qb.DocType("Sales Order Item")
    pending_so = (
        frappe.qb.from_(sod)
        .join(so).on(so.name == sod.parent)
        .select(Sum(sod.qty - sod.delivered_qty))
        .where((sod.parenttype == "Sales Order") & (so.docstatus == 1) & (so.status != "Closed"))
        .where((sod.qty > sod.delivered_qty) & (sod.name == so_item))
        .run()
    )
    return flt(pending_so[0][0]) if pending_so else 0


def get_total_sales_orders(customer, frm_date, to_date):
    totals = get_sales_order_totals([customer], frm_date, to_date)
    return [totals.get(customer) or frappe._dict(total_net_amt=None, so=0)]


def compare_cust_pmt_terms(custd, enforce=0):
    cust_rating = get_customer_sales_rating(custd.name)
    if not custd.payment_terms:
        if cust_rating > 0:
            frappe.throw(f"Payment Terms are Mandatory for "
                f"{frappe.get_desk_link('Customer', custd.name)}")
        else:
            def_pmt = frappe.get_value("RIGPL Settings", "RIGPL Settings", "default_payment_terms")
            custd.payment_terms = def_pmt

    else:
        ptd = frappe.get_doc("Payment Terms Template", custd.payment_terms)
        if ptd.minimum_sales_rating > cust_rating:
            msg = f"For {frappe.get_desk_link('Customer', custd.name)}: Payment Terms Selected \
            is {custd.payment_terms} which needs Min Sales Rating of {ptd.minimum_sales_rating}<br>\
            But Customer has a Sales Rating of Only {cust_rating}. <br>\
            Consider Changing the Payment Terms to a More Appropriate one Based on \
            Customer Sales Rating"
            frappe.msgprint(msg, raise_exception=enforce)


def get_customer_sales_rating(cust_name):
    sales_rating = 0
    period = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "years_to_consider"))
    if period == 0:
        period = 2
    to_date = today()
    from_date = add_months(to_date, months=12*period*(-1))
    annual_base = get_base_annual_sales(from_date, to_date)

    invoices = get_total_invoices_and_amount(cust_name, from_date, to_date)
    if invoices:
        tot_sales = flt(invoices[0]["total_net_amt"])
    else:
        tot_sales = 0

    sales_rating = min(int(tot_sales/annual_base/period*100), 100)
    return sales_rating


def get_customer_rating_factor(customer_dict, base_years=5):
    settings = frappe.get_cached_doc("RIGPL Settings", "RIGPL Settings")
    # Calculate Age Factor
    days_since = customer_dict["days_since"]
    age_wt = flt(settings.age_weightage)
    age_factor = min((days_since / (base_years*365))*100, 100)
    wt_age_factor = min(int(age_factor*(age_wt/100)), 100)
    customer_dict["age_factor"] = age_factor

    # Calculate Sales Factor
    annual_base = customer_dict["base_annual_sales"]
    period = customer_dict["period"]
    sal_wt = flt(settings.sales_weightage)
    tot_sales = customer_dict["total_sales"]
    sales_factor = min(int(tot_sales*365*100/annual_base/period), 100)
    wt_sales_factor = int(sales_factor * (sal_wt/100))
    customer_dict["sales_factor"] = sales_factor

    # Calculate Payment Factor
    pmt_wt = flt(settings.payment_weightage)
    pmt_factor = customer_dict["pmt_factor"] * 10
    wt_pmt_factor = int(pmt_factor * (pmt_wt / 100))
    customer_dict["pmt_factor"] = pmt_factor

    # Calculate Average Orders Given in a Month
    min_monthly_orders = flt(settings.minimum_orders_per_month)
    no_of_orders = customer_dict["total_so"]
    monthly_orders = int(no_of_orders * 365 / period / 12)
    customer_dict["avg_monthly_orders"] = monthly_orders

    if monthly_orders < min_monthly_orders and min_monthly_orders > 0:
        monthly_orders = min_monthly_orders

    # Calculate Total Factor
    if no_of_orders == 0:
        factor = 0
    else:
        if min_monthly_orders > 0:
            factor = wt_sales_factor + wt_age_factor + wt_pmt_factor - (min_monthly_orders/10)
            # Old factor calculation Formula
            # factor = int(tot_sales * age_factor / period / monthly_orders /1000)
        else:
            factor = wt_sales_factor + wt_age_factor + wt_pmt_factor
            # Old Factor Calculation formula
            # factor = int(tot_sales * age_factor / period /1000)
    customer_dict["total_rating"] = factor


def get_total_company_sales(frm_date, to_date):
    """
    Returns the Net Total of the submitted Sales Invoices in the period, with the same
    filters as the sales of a customer (get_invoice_totals)
    """
    si = frappe.qb.DocType("Sales Invoice")
    tot_sales = (
        frappe.qb.from_(si)
        .select(Sum(si.base_net_total))
        .where((si.docstatus == 1) & (si.base_net_total > 0))
        .where((si.posting_date >= frm_date) & (si.posting_date <= to_date))
        .run()
    )
    return flt(tot_sales[0][0])


def get_base_annual_sales(from_date, to_date):
    """
    Returns the annual sales that give a customer the full Sales Factor. It is a percent of the
    company sales of the period when RIGPL Settings says so, else the fixed Base Annual Sales.
    """
    settings = frappe.get_cached_doc("RIGPL Settings", "RIGPL Settings")
    if settings.get("base_sales_from_company_sales"):
        days = max((getdate(to_date) - getdate(from_date)).days, 1)
        annual_sales = get_total_company_sales(from_date, to_date) * 365 / days
        annual_base = annual_sales * flt(settings.get("base_sales_percent")) / 100
    else:
        annual_base = flt(settings.base_annual_sales)
    return annual_base or 100000


def get_sales_order_totals(customers, from_date, to_date):
    """
    Returns {customer: frappe._dict(total_net_amt, so)} for the submitted Sales Orders in the
    period, like get_total_sales_orders but for many customers
    """
    so = frappe.qb.DocType("Sales Order")
    totals = {}
    for chunk in chunks(customers):
        rows = (
            frappe.qb.from_(so)
            .select(
                so.customer,
                Sum(so.base_net_total).as_("total_net_amt"),
                Count(so.name).as_("so"),
            )
            .where((so.docstatus == 1) & (so.base_net_total > 0) & so.customer.isin(chunk))
            .where((so.transaction_date >= from_date) & (so.transaction_date <= to_date))
            .groupby(so.customer)
            .run(as_dict=True)
        )
        totals.update({row.customer: row for row in rows})
    return totals


def get_invoice_totals(customers, from_date, to_date):
    """
    Returns {customer: frappe._dict(total_net_amt, invoices)} for the submitted Sales Invoices
    in the period, like get_total_invoices_and_amount but for many customers
    """
    si = frappe.qb.DocType("Sales Invoice")
    totals = {}
    for chunk in chunks(customers):
        rows = (
            frappe.qb.from_(si)
            .select(
                si.customer,
                Sum(si.base_net_total).as_("total_net_amt"),
                Count(si.name).as_("invoices"),
            )
            .where((si.docstatus == 1) & (si.base_net_total > 0) & si.customer.isin(chunk))
            .where((si.posting_date >= from_date) & (si.posting_date <= to_date))
            .groupby(si.customer)
            .run(as_dict=True)
        )
        totals.update({row.customer: row for row in rows})
    return totals


def get_first_order_dates(customers, amt=0):
    """
    Returns {customer: date of the first submitted Sales Order above amt}
    """
    so = frappe.qb.DocType("Sales Order")
    first_orders = {}
    for chunk in chunks(customers):
        rows = (
            frappe.qb.from_(so)
            .select(so.customer, Min(so.transaction_date))
            .where((so.docstatus == 1) & (so.base_net_total > amt) & so.customer.isin(chunk))
            .groupby(so.customer)
            .run()
        )
        first_orders.update(dict(rows))
    return first_orders


def get_customer_rating_from_pts(tot_rating_pts):
    # Currently the assumption is that the maximum points earned is 0-10k for every rating 100pts are there.
    # But since there is less people above 5k the ranges are defined differently.
    divisor = flt(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings", "rating_divisor"))
    if divisor == 0:
        divisor = 1
    return min(int(tot_rating_pts/ divisor), 100)


def get_priority_for_so(it_name, prd_qty, short_qty, so_detail=None, so_lines=None):
    """
    Returns the priority from the open Sales Order lines of the item. Pass `so_lines`
    (get_open_so_lines) when checking many items.
    """
    so_date_value_dict = get_so_date_value(
        it_name=it_name, prd_qty=prd_qty, short_qty=short_qty, so_detail=so_detail, so_lines=so_lines
    )
    priority = prioritize_sales_order(so_date_value_dict)
    return priority


def get_so_date_value(it_name, prd_qty, short_qty=0, so_detail=None, so_lines=None):
    if so_lines is None:
        so_lines = get_open_so_lines([it_name]).get(it_name, [])
    return [
        frappe._dict(row, prd_qty=prd_qty, shortage=short_qty)
        for row in so_lines
        if not so_detail or row.so_detail == so_detail
    ]


def get_open_so_lines(items):
    """
    Returns {item: [open Sales Order lines]}, the newest Sales Order first. The SO Items are read
    by item_code and the Sales Orders by name in 2 queries, because a join makes MariaDB scan all
    the Sales Orders.
    """
    sod = frappe.qb.DocType("Sales Order Item")
    so_lines = []
    for chunk in chunks(items):
        so_lines += (
            frappe.qb.from_(sod)
            .select(
                sod.parent.as_("name"), sod.name.as_("so_detail"), sod.item_code,
                sod.qty.as_("order_qty"),
                (sod.base_rate * (sod.qty - sod.delivered_qty)).as_("balance_amt"),
            )
            .where(sod.parenttype == "Sales Order")
            .where(sod.item_code.isin(chunk))
            .where(sod.qty > sod.delivered_qty)
            .run(as_dict=True)
        )
    so_dates = {}
    for chunk in chunks(row.name for row in so_lines):
        so_dates.update(
            frappe.get_all(
                "Sales Order",
                filters={"name": ("in", chunk), "docstatus": 1, "status": ("!=", "Closed")},
                fields=["name", "transaction_date"],
                as_list=True,
            )
        )
    lines = {}
    for row in so_lines:
        if row.name in so_dates:
            row.so_date = so_dates[row.name]
            lines.setdefault(row.item_code, []).append(row)
    for rows in lines.values():
        # Newest Sales Order first, then by name
        rows.sort(key=lambda row: row.name)
        rows.sort(key=lambda row: row.so_date, reverse=True)
    return lines


def prioritize_sales_order(so_dict):
    factor = 0
    # Factors to prioritize are SO Date means older SO should hold Bigger Urgency
    # Also the value of the SO Item should hold higher urgency.
    # So we give a multiplier Value * Days difference for date
    for d in so_dict:
        prd_qty = d.prd_qty
        shortage = d.shortage
        days_diff = datetime.date.today() - d.so_date
        days_diff = days_diff.days + 1 # For same date SO the factor would be 1
        factor += days_diff * (d.balance_amt + 1) * (shortage/(prd_qty + 1))
    # Factor would be 1,000,000 for order value 100,000 and 10 days old
    # Factor would be 500,000 for order value 50,000 and 10 days old
    # Factor would be 250,000 for order value 25,000 and 10 days old
    # Factor would be 150,000 for order value 15,000 and 10 days old
    # Factor would be 100,000 for order value 10,000 and 10 days old
    # Factor would be 50,000 for order value 5,000 and 10 days old
    # Factor would be 25,000 for order value 2,500 and 10 days old
    # Factor would be 10,000 for order value 1,000 and 10 days old
    # Factor would be 5,000 for order value 500 and 10 days old
    # Factor would be 1,000 for order value 100 and 10 days old
    if factor > 1000000:
        # Value of Order is 10,000 * 100 days or 100,000 * 10 days
        return 1
    elif factor > 500000:
        return 2
    elif factor > 250000:
        return 3
    elif factor > 150000:
        return 4
    elif factor > 100000:
        return 5
    elif factor > 50000:
        return 6
    elif factor > 25000:
        return 7
    elif factor > 10000:
        return 8
    elif factor > 5000:
        return 9
    elif factor > 1000:
        return 10
    elif factor == 0:
        return 999
    else:
        return 11


def get_completed_jc_qtys(keys):
    """
    Returns {(production_item, operation, sales_order_item): completed qty of the submitted
    Process Job Cards}
    """
    jc = frappe.qb.DocType("Process Job Card RIGPL")
    qtys = {}
    for chunk in chunks(keys):
        for item, operation, so_detail, qty in (
            frappe.qb.from_(jc)
            .select(jc.production_item, jc.operation, jc.sales_order_item, Sum(jc.total_completed_qty))
            .where(jc.docstatus == 1)
            .where(Tuple(jc.production_item, jc.operation, jc.sales_order_item).isin(
                [Tuple(*key) for key in chunk]))
            .groupby(jc.production_item, jc.operation, jc.sales_order_item)
            .run()
        ):
            qtys[(item, operation, so_detail)] = flt(qty)
    return qtys


def get_completed_qty_of_jc_for_operation(item, operation, so_detail=None):
    return get_completed_jc_qtys([(item, operation, so_detail)]).get((item, operation, so_detail), 0)


def get_bins_with_wh_type(items):
    """
    Returns {item: [Bin rows of enabled warehouses with warehouse_type]}
    """
    bn = frappe.qb.DocType("Bin")
    wh = frappe.qb.DocType("Warehouse")
    bins = {}
    for chunk in chunks(items):
        for row in (
            frappe.qb.from_(bn)
            .join(wh).on(bn.warehouse == wh.name)
            .select(
                bn.item_code, bn.warehouse, bn.reserved_qty, bn.actual_qty,
                bn.reserved_qty_for_production, wh.warehouse_type,
            )
            .where((wh.disabled == 0) & bn.item_code.isin(chunk))
            .run(as_dict=True)
        ):
            bins.setdefault(row.item_code, []).append(row)
    return bins


def dead_stock_order_booking(doc):
    """Validation to Disallow Booking of Orders for More than Available Quantity for Items in Dead Stock"""
    bins = get_bins_with_wh_type([it.item_code for it in doc.items])
    for it in doc.items:
        qty_dict = bins.get(it.item_code, [])
        check_dead = 0
        for wh in qty_dict:
            if wh.warehouse_type == 'Dead Stock' and wh.actual_qty > 0:
                check_dead = 1
        if check_dead == 1:
            tot_actual_qty = 0
            tot_reserved_qty = 0
            tot_reserved_qty_for_production = 0
            for wh in qty_dict:
                if wh.warehouse_type in ('Finished Stock', 'Dead Stock'):
                    tot_actual_qty += wh.actual_qty
                    tot_reserved_qty += wh.reserved_qty
                    tot_reserved_qty_for_production += wh.reserved_qty_for_production
            allowed_so_qty = tot_actual_qty - tot_reserved_qty - tot_reserved_qty_for_production
            if it.qty > allowed_so_qty:
                frappe.throw('Row# {}, {} is in Dead Stock and Allowed Qty for SO Booking = {}'.
                             format(it.idx, frappe.get_desk_link('Item', it.item_code), allowed_so_qty))


def validate_made_to_order_items(doc):
    '''
    This validation basically checks if an Item is Made to Order or Not if Item is Made to Order or Special Item
    Then the system would check if all the Process Sheet Job Cards are completed or Not.
    '''
    if doc.bypass_made_to_order_check == 1:
        return
    made_to_order = set(frappe.get_all("Item", pluck="name", filters={
        "name": ["in", [it.item_code for it in doc.items]], "made_to_order": 1}))
    special = get_special_item_data([it for it in doc.items if it.item_code in made_to_order])
    for it in doc.items:
        if it.item_code in made_to_order:
            # Check if the Item as per the Process Sheet or Not
            check_special_item(doc, it, special)
        validate_warehouse(doc, it)


def get_special_item_data(rows):
    """
    Returns {"pro_sheets": {(item, so_detail): Process Sheet}, "final_ops": {Process Sheet:
    [final operations]}, "completed": get_completed_jc_qtys} for the made to order rows
    """
    ps = frappe.qb.DocType("Process Sheet")
    pairs = [(row.item_code, row.so_detail) for row in rows]
    pro_sheets = {}
    for chunk in chunks(pairs):
        for name, item, so_detail in (
            frappe.qb.from_(ps)
            .select(ps.name, ps.production_item, ps.sales_order_item)
            .where(ps.docstatus == 1)
            .where(Tuple(ps.production_item, ps.sales_order_item).isin([Tuple(*pair) for pair in chunk]))
            .orderby(ps.name)
            .run()
        ):
            pro_sheets.setdefault((item, so_detail), name)
    final_ops = {}
    for op in frappe.get_all("BOM Operation", fields=["parent", "operation"], order_by="idx",
            filters={"parenttype": "Process Sheet", "final_operation": 1,
                "parent": ["in", list(pro_sheets.values()) or [""]]}):
        final_ops.setdefault(op.parent, []).append(op.operation)
    keys = [(item, operation, so_detail) for (item, so_detail), name in pro_sheets.items()
        for operation in final_ops.get(name, [])]
    return {"pro_sheets": pro_sheets, "final_ops": final_ops, "completed": get_completed_jc_qtys(keys)}


def check_special_item(doc, row, special):
    pro_sheet = special["pro_sheets"].get((row.item_code, row.so_detail))
    if not pro_sheet:
        frappe.throw("There is No Processing Done for {} in Row# {} for {}".
                     format(row.item_code, row.idx, frappe.get_desk_link(doc.doctype, doc.name)))
    # If there is a Submitted Process Sheet then Check if all the Job Cards are Submitted for the Same Quantity
    for operation in special["final_ops"].get(pro_sheet, []):
        qty_completed = special["completed"].get((row.item_code, operation, row.so_detail), 0)
        if row.qty > flt(qty_completed):
            frappe.throw("Only allowed to Submit Qty= {} for Row# {} for {}".
                         format(flt(qty_completed), row.idx, frappe.get_desk_link(doc.doctype, doc.name)))


def validate_special_items(doc, row):
    check_special_item(doc, row, get_special_item_data([row]))


def validate_warehouse(doc, row):
    """Only Allow from Finished Stock Warehouse"""
    wh_doc = frappe.get_doc('Warehouse', row.warehouse)
    if wh_doc.warehouse_type != 'Finished Stock':
        frappe.throw("In {}, Row# {} and {} the {} selected is Not Finished Stock Warehouse".
            format(frappe.get_desk_link(doc.doctype, doc.name), row.idx, frappe.get_desk_link('Item', row.item_code),
                   frappe.get_desk_link('Warehouse', row.warehouse)))
    elif wh_doc.disabled == 1:
        frappe.throw("In {}, Row# {} and {} the {} selected is Disabled Warehouse".
            format(frappe.get_desk_link(doc.doctype, doc.name), row.idx, frappe.get_desk_link('Item', row.item_code),
                   frappe.get_desk_link('Warehouse', row.warehouse)))


def validate_address_google_update(add_doc_name):
    add_doc = frappe.get_doc('Address', add_doc_name)
    if not add_doc.json_reply and add_doc.dont_update_from_google != 1:
        frappe.throw('Address {} is Not Updated from Google, Please Open and Save '
                     'the Address once'.format(add_doc.name))


def copy_address_and_check(document):
    if document.doctype == 'Delivery Note':
        so_field = "against_sales_order"
    elif document.doctype == 'Sales Invoice':
        so_field = 'sales_order'
    for items in document.items:
        if items.get(so_field):
            so_doc = frappe.get_doc("Sales Order", items.get(so_field))
            if document.customer_address != so_doc.customer_address:
                frappe.throw("Customer Address mentioned in {} {} does not match with Customer Address of SO# {} "
                             "mentioned in Row# {}".format(document.doctype, document.name, items.get(so_field),
                                                           items.idx))
            if document.shipping_address_name != so_doc.shipping_address_name:
                frappe.throw("Shipping Address mentioned in {} {} does not match with Shipping Address of SO# {} "
                             "mentioned in Row# {}".format(document.doctype, document.name, items.get(so_field),
                                                           items.idx))


def check_strict_po_rules(document):
    follow_rules = 0
    cust_rule = 0
    so_rule = 0
    so_list = []
    if document.doctype == 'Delivery Note':
        so_field = "against_sales_order"
    elif document.doctype == 'Sales Invoice':
        so_field = 'sales_order'
    cust_doc = frappe.get_doc("Customer", document.customer)

    if cust_doc.follow_strict_po_rules == 1:
        follow_rules = 1
        cust_rule = 1

    for it in document.items:
        if it.get(so_field):
            so_doc = frappe.get_doc('Sales Order', it.get(so_field))
            if so_doc.follow_strict_po_rules == 1:
                follow_rules = 1
                so_rule = 1
            if it.idx == 1:
                so_list.append(it.get(so_field))
            elif it.idx > 1 and follow_rules == 1:
                if it.get(so_field) not in so_list:
                    frappe.throw("{} Follows Strict PO Rules for {} hence Row {} is Rejected. Make new {} "
                                 "for SO# {}".
                                 format(frappe.get_desk_link("Customer", document.customer),
                                        frappe.get_desk_link("Sales Order", it.get(so_field)), it.idx, document.doctype,
                                        frappe.get_desk_link("Sales Order", it.get(so_field))))


def get_hsn_code(row_dict):
    custom_tariff = frappe.db.get_value("Item", row_dict.item_code, "customs_tariff_number")
    if custom_tariff:
        if len(custom_tariff) >= 6:
            row_dict.gst_hsn_code = custom_tariff
        else:
            frappe.throw(("Item Code {0} in line# {1} has a Custom Tariff {2} which is Less than 6 digit, please get the "
                          "Custom Tariff corrected").format(row_dict.item_code, row_dict.idx, custom_tariff))
    else:
        frappe.throw("Item Code {0} in line# {1} does not have linked Customs Tariff in Item Master".format(
            row_dict.item_code, row_dict.idx))


def get_item_price_rows(pairs, selling_only=False):
    """
    Returns {(item_code, price_list): first Item Price row (price_list_rate, currency)}
    """
    ip = frappe.qb.DocType("Item Price")
    prices = {}
    for chunk in chunks([pair for pair in pairs if all(pair)]):
        query = (
            frappe.qb.from_(ip)
            .select(ip.item_code, ip.price_list, ip.price_list_rate, ip.currency)
            .where(Tuple(ip.item_code, ip.price_list).isin([Tuple(*pair) for pair in chunk]))
        )
        if selling_only:
            query = query.where(ip.selling == 1)
        for row in query.run(as_dict=True):
            prices.setdefault((row.item_code, row.price_list), row)
    return prices


def get_item_price(item_name, price_list):
    """
    If Price List Rate exists then returns the Price List Rate else returns False
    """
    row = get_item_price_rows([(item_name, price_list)]).get((item_name, price_list))
    return row.price_list_rate if row else False


def check_get_pl_rates(document, rows):
    pl = frappe.qb.DocType("Price List")
    disabled = set()
    for chunk in chunks([row.price_list for row in rows]):
        disabled.update(name for (name,) in frappe.qb.from_(pl).select(pl.name)
            .where(pl.name.isin(chunk) & (pl.disable_so == 1)).run())
    prices = get_item_price_rows([(row.item_code, row.price_list) for row in rows], selling_only=True)
    for row_dict in rows:
        if row_dict.price_list in disabled:
            frappe.throw("Sales Order Booking Disabled for {} at Row# {}".format(row_dict.price_list, row_dict.idx))
        item_pl_rate = prices.get((row_dict.item_code, row_dict.price_list))
        if item_pl_rate:
            if row_dict.price_list_rate != item_pl_rate.price_list_rate and document.currency == item_pl_rate.currency:
                row_dict.price_list_rate = item_pl_rate.price_list_rate
        else:
            frappe.msgprint("In {}# {} at Row# {} and Item Code: {} Price List Rate is Not Defined".format(
                document.doctype, document.name, row_dict.idx, row_dict.item_code))


def check_get_pl_rate(document, row_dict):
    check_get_pl_rates(document, [row_dict])


def get_total_invoices_and_amount(customer, from_date, to_date):
    totals = get_invoice_totals([customer], from_date, to_date)
    return [totals.get(customer) or frappe._dict(total_net_amt=None, invoices=0)]


def check_gst_rules(doc, bill_add_name, taxes_name):
    bill_add_doc = frappe.get_doc("Address", bill_add_name)
    template_doc = frappe.get_doc("Sales Taxes and Charges Template", taxes_name)

    bill_state = bill_add_doc.state_rigpl
    bill_country = bill_add_doc.country

    # Check series of Tax with the Series Selected for Invoice
    series_regex = replace_java_chars(template_doc.series)
    if series_regex:
        if 'or' in series_regex:
            ser_regex = series_regex.split("or")
        else:
            ser_regex = [series_regex]
        series_regex_pass = 0
        for d in ser_regex:
            p = re.compile(d.strip())
            if not p.match(doc.name):
                pass
            else:
                series_regex_pass = 1
        if series_regex_pass != 1:
            frappe.throw("{}: is not as per the defined Series in {}".
                         format(doc.name, frappe.get_desk_link(template_doc.doctype, template_doc.name)))
    else:
        frappe.throw("Series Regex Not Defined for {} and {}".
                     format(frappe.get_desk_link(doc.doctype, doc.name),
                            frappe.get_desk_link(template_doc.doctype, template_doc.name)))

    if taxes_name != 'OGL':
        # Check if Shipping State is Same as Template State then check if the tax template is LOCAL
        # Else if the States are different then the template should NOT BE LOCAL
        if bill_state == template_doc.state and template_doc.is_export != 1:
            if template_doc.is_local_sales != 1:
                frappe.throw(("Selected Tax {0} is NOT LOCAL Tax but Shipping Address is in Same State {1}, "
                              "hence either change Shipping Address or Change the Selected Tax").format(taxes_name,
                                                                                                        bill_state))
        elif bill_country == 'India' and bill_state != template_doc.state:
            if template_doc.is_local_sales == 1:
                frappe.throw(("Selected Tax {0} is LOCAL Tax but Shipping Address is in Different State {1}, "
                              "hence either change Shipping Address or Change the Selected Tax").format(taxes_name,
                                                                                                        bill_state))
        elif bill_country != 'India':  # Case of EXPORTS
            if template_doc.state is not None and template_doc.is_export != 1:
                frappe.throw("Selected Tax {0} is for Indian Sales but Shipping Address is in Different Country {1}, "
                             "hence either change Shipping Address or Change the Selected Tax".format(taxes_name,
                                                                                                      bill_country))

def disallow_qty_change(so_doc):
    """
    Don't allow change in Qty after submission of Sales Order
    """
    if so_doc.docstatus == 1:
        for itm in so_doc.items:
            old_qty = frappe.db.get_value("Sales Order Item", itm.name, "qty")
            frappe.msgprint(f"For Row# {itm.idx} Previous Qty = {old_qty} and New Qty = {itm.qty} and SOI name = {itm.name}")
