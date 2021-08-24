# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, fmt_money
from erpnext.accounts.utils import get_balance_on
from .sales_utils import get_customer_sales_rating
from datetime import datetime


def check_overdue_receivables(cu_doc):
    '''
    If customer sales rating lower than Pmt Terms Rating then don't allow Submission after due date
    and leeway period only allowed for Credit Controller.
    If customer sales rating above pmt rating then leeway should be multiple by the factor to check
    also if Rating is Over the min reqd then Non Credit Controller can do upto max days
    '''
    current_balance = get_balance_on(party_type=cu_doc.doctype, party=cu_doc.name)
    is_cc = get_credit_controller()
    pmt_doc = get_pmt_doc_for_customer(cu_doc)
    max_days_allowed = get_max_credit_days(cu_doc, is_cc)
    if current_balance > 0:
        si_dict = get_overdue_si(cu_doc.name)
        over_due_si = []
        if si_dict:
            if pmt_doc.credit_given == 1:
                for si in si_dict:
                    if si.since_days > max_days_allowed:
                        od_si = [f"Overdue {frappe.get_desk_link('Sales Invoice', si.name)}<br>"
                        f"Outstanding Amount = {fmt_money(si.outstanding_amount)} Since "
                        f"{si.since_days} Days.<br>Whereas as per the Payment Terms After "
                        f"{max_days_allowed} Days Due Account Gets Locked.<br>"
                        f"Hence cannot proceed or Bypass Credit Check."]
                        over_due_si.append(od_si)
                if over_due_si:
                    frappe.msgprint(over_due_si, as_table=1, raise_exception=1)
            else:
                frappe.msgprint(f"For {frappe.get_desk_link('Customer', cu_doc.name)} for "
                    f"Payment Terms {pmt_doc.name} Credit Not Allowed but there is Balance "
                    f"Pending for Amount = {fmt_money(current_balance)}",
                    raise_exception=1)


def get_pmt_doc_for_customer(cust_doc):
    if cust_doc.payment_terms:
        pmt_doc = frappe.get_doc("Payment Terms Template", cust_doc.payment_terms)
    else:
        def_pmt = frappe.get_value("RIGPL Settings", "RIGPL Settings", "default_payment_terms")
        pmt_doc = frappe.get_doc("Payment Terms Template", def_pmt)
    return pmt_doc


def get_max_credit_days(cust_doc, is_cc=0):
    cust_rat = get_customer_sales_rating(cust_doc.name)
    pmt_doc = get_pmt_doc_for_customer(cust_doc)
    if cust_rat > pmt_doc.minimum_sales_rating:
        # Max Days would be Av Credit + Leeway * Cust Rat/Min Rat
        max_days = int(pmt_doc.average_credit_days + pmt_doc.leeway_days * (cust_rat/pmt_doc.minimum_sales_rating))
    else:
        # If credit controller = 1 then max_days= credit+leeway else only credit days
        if is_cc == 1:
            max_days = int(pmt_doc.average_credit_days + pmt_doc.leeway_days * (cust_rat/pmt_doc.minimum_sales_rating))
        else:
            max_days = int(pmt_doc.average_credit_days)
    return max_days



def get_credit_controller():
    user_roles = frappe.get_roles(frappe.session.user)
    credit_controller = frappe.get_value("Accounts Settings", "Accounts Settings",
        "credit_controller")
    if not credit_controller:
        credit_controller = "System Manager"
    if credit_controller in user_roles:
        return 1
    else:
        return 0


def get_overdue_si(cust_name):
    cur_prec = flt(frappe.get_value("System Settings", "System Settings", "currency_precision"))
    out_amt = 1/pow(10, cur_prec)
    si_dict = frappe.db.sql("""SELECT name, posting_date, outstanding_amount,
        DATEDIFF(CURDATE(), posting_date) as since_days
        FROM `tabSales Invoice` WHERE docstatus=1
        AND outstanding_amount > %s AND customer='%s'
        ORDER BY posting_date ASC""" % (out_amt, cust_name), as_dict=1)
    return si_dict


def get_average_payment_days(customer, from_date, to_date):
    invoice_list = frappe.db.sql("""SELECT customer, name, base_net_total as net_amt, base_grand_total as grand_total,
    posting_date, due_date FROM `tabSales Invoice` WHERE docstatus = 1 AND base_grand_total > 0 AND customer = '%s'
    AND is_pos = 0 AND posting_date >= '%s' AND posting_date <= '%s'""" % (customer, from_date, to_date), as_dict=1)
    if invoice_list:
        entries = frappe.db.sql("""SELECT voucher_type, voucher_no, party_type, party, posting_date, debit, credit,
        remarks, against_voucher FROM `tabGL Entry` WHERE party_type="Customer" AND voucher_type in
        ('Journal Entry', 'Payment Entry') AND party = '%s' """ % customer, as_dict=1)
        for inv in invoice_list:
            inv["total_pmt_days"] = 0
            inv["paid_amt"] = 0
            for d in entries:
                # Average days formula = p1 * d1 + p2 * d2 ... / total_amt
                average_days = 0
                total_days = 0
                if d.against_voucher == inv.name:
                    if d.reference_type == "Purchase Invoice":
                        payment_amount = flt(d.debit) or -1 * flt(d.credit)
                    else:
                        payment_amount = flt(d.credit) or -1 * flt(d.debit)
                    payment_days = (d.posting_date - inv.posting_date).days
                    inv["total_pmt_days"] += payment_days * payment_amount
                    inv["paid_amt"] += payment_amount
    if invoice_list:
        avg_days_invoice = get_average_from_all_invoices(invoice_list)
        return avg_days_invoice.avg_days
    else:
        return 0


def get_average_from_all_invoices(invoice_list):
    avg_days = frappe._dict()
    payment_days, total_pmt_days, total_invoice_amt, total_paid = 0,0,0,0
    total_unpaid, total_unpaid_days = 0,0
    for inv in invoice_list:
        avg_days["customer"] = inv.customer
        unpaid_days = (datetime.now().date() - inv.posting_date).days
        unpaid_amt = inv.grand_total - inv.paid_amt
        total_invoice_amt += inv.grand_total
        total_paid += inv.paid_amt
        total_pmt_days += inv.total_pmt_days
        total_unpaid += inv.grand_total - inv.paid_amt
        total_unpaid_days += unpaid_days * unpaid_amt
    average_days = int((total_pmt_days + total_unpaid_days) / (total_paid + total_unpaid))
    avg_days["avg_days"] = average_days
    return avg_days


def get_customer_pmt_factor(customer_dict):
    avg_pmt_days = customer_dict["avg_pmt_days"]
    if avg_pmt_days < 15:
        pmt_factor = 10
    elif avg_pmt_days < 30:
        pmt_factor = 8
    elif avg_pmt_days < 45:
        pmt_factor = 7
    elif avg_pmt_days < 60:
        pmt_factor = 6
    elif avg_pmt_days < 75:
        pmt_factor = 5
    elif avg_pmt_days < 90:
        pmt_factor = 4
    elif avg_pmt_days < 105:
        pmt_factor = 3
    elif avg_pmt_days < 120:
        pmt_factor = 2
    else:
        pmt_factor = 1
    return pmt_factor
