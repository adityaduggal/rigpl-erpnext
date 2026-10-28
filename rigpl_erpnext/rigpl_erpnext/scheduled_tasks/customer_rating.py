# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
import datetime
from frappe.utils import add_days, flt
from frappe.utils.background_jobs import enqueue
from ...utils.accounts_receivable_utils import get_average_payment_days_by_customer, \
    get_customer_pmt_factor
from ...utils.batch_write_utils import bulk_set_values
from ...utils.sales_utils import get_base_annual_sales, get_customer_rating_factor, \
    get_customer_rating_from_pts, get_first_order_dates, get_invoice_totals, \
    get_sales_order_totals


def enqueue_job():
    enqueue(execute, queue="long", timeout=7200)


def execute():
    st_time = time.time()
    customers = frappe.get_all("Customer", fields=["name", "customer_rating"], order_by="name")
    old_ratings = {cu.name: cu.customer_rating for cu in customers}
    rated = build_customer_ratings([frappe._dict(name=cu.name) for cu in customers])
    new_ratings = {cu.name: cu.customer_rating for cu in rated}
    changes = bulk_set_values("Customer", "customer_rating", new_ratings, old_ratings)
    tot_time = round(time.time() - st_time)
    print(f"Customer Rating Changed for {len(changes)} of {len(customers)} Customers. "
        f"Total Time {tot_time} seconds")


def build_customer_rating(cust_dict, from_date=None, to_date=None, fov=None, days=None):
    return build_customer_ratings([cust_dict], from_date=from_date, to_date=to_date, fov=fov,
        days=days)[0]


def build_customer_ratings(customers, from_date=None, to_date=None, fov=None, days=None):
    """
    Adds the rating values to each customer dict (which needs the key name) and returns the
    list. All customers are read with a fixed number of queries for each chunk of customers.
    """
    settings = frappe.get_cached_doc("RIGPL Settings", "RIGPL Settings")
    if not days:
        years = flt(settings.years_to_consider)
    else:
        years = days/365
    if years == 0:
        years = 5
    if not fov:
        fov = flt(settings.minimum_first_order)
    if fov == 0:
        fov = 10000
    if not days:
        days = years * 365
    if not to_date:
        to_date = datetime.datetime.today().date()
    if not from_date:
        from_date = add_days(to_date, days*(-1))

    names = [cu.name for cu in customers]
    base_annual_sales = get_base_annual_sales(from_date, to_date)
    avg_pmt_days = get_average_payment_days_by_customer(names, from_date, to_date)
    first_orders = get_first_order_dates(names, fov)
    sales_orders = get_sales_order_totals(names, from_date, to_date)
    invoices = get_invoice_totals(names, from_date, to_date)
    for cust_dict in customers:
        cust_dict["avg_pmt_days"] = avg_pmt_days.get(cust_dict.name, 0)
        cust_dict["pmt_factor"] = get_customer_pmt_factor(cust_dict)
        cust_dict["base_annual_sales"] = base_annual_sales
        fo_date = first_orders.get(cust_dict.name, to_date)
        cust_dict["period"] = days
        cust_dict["days_since"] = (to_date - fo_date).days
        so = sales_orders.get(cust_dict.name, {})
        cust_dict["total_orders"] = flt(so.get("total_net_amt"))
        cust_dict["total_so"] = flt(so.get("so"))
        si = invoices.get(cust_dict.name, {})
        cust_dict["total_sales"] = flt(si.get("total_net_amt"))
        cust_dict["total_invoices"] = flt(si.get("invoices"))
        get_customer_rating_factor(cust_dict, years)
        cust_dict["customer_rating"] = get_customer_rating_from_pts(cust_dict["total_rating"])
    return customers
