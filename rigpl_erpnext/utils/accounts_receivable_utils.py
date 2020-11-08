# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from datetime import datetime


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
                average_days  = 0
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



def get_total_invoices_and_amount(customer, from_date, to_date):
    invoices = frappe.db.sql("""SELECT SUM(base_net_total) AS total_net_amt, COUNT(name) AS invoices
    FROM `tabSales Invoice` WHERE docstatus = 1 AND base_net_total > 0 AND customer = '%s' AND posting_date >= '%s' 
    AND posting_date <= '%s'""" % (customer, from_date, to_date), as_dict=1)
    return invoices
