# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, time, datetime
from frappe.utils import add_days, flt
from ...utils.accounts_receivable_utils import get_average_payment_days, get_total_invoices_and_amount, \
    get_customer_pmt_factor
from ...utils.sales_utils import get_total_sales_orders, get_first_order, get_customer_rating_factor


def execute():
    st_time = time.time()
    customers = frappe.db.sql("""SELECT name FROM `tabCustomer` ORDER BY name""", as_dict=1)
    customers_rated_list = []
    for cu in customers:
        customers_with_rating = build_customer_rating(cu)
        customers_rated_list.append(customers_with_rating.copy())
    customers_rated_list = sorted(customers_rated_list, key=lambda i:(i["total_rating"]))
    for cu in customers_rated_list:
        print(cu)
    # print(customers)
    end_time = time.time()
    tot_time = round(end_time - st_time)
    print(f"Total Time {tot_time} seconds")

def build_customer_rating(cust_dict, from_date=None, to_date=None, fov=10000, days=5*365):
    if not to_date:
        to_date = datetime.datetime.today().date()
    if not from_date:
        from_date = from_date = add_days(to_date, days*(-1))
    cust_dict["avg_pmt_days"] = get_average_payment_days(cust_dict.name, from_date, to_date)
    cust_dict["pmt_factor"] = get_customer_pmt_factor(cust_dict)
    first_order = get_first_order(cust_dict.name, fov)
    if first_order:
        fo_date = first_order[0].date
    else:
        fo_date = to_date
    days_since = (to_date - fo_date).days
    cust_dict["period"] = days
    cust_dict["days_since"] = days_since
    sales_orders = get_total_sales_orders(cust_dict.name, from_date, to_date)
    if sales_orders:
        cust_dict["total_orders"] = flt(sales_orders[0]["total_net_amt"])
        cust_dict["total_so"] = flt(sales_orders[0]["so"])
    else:
        cust_dict["total_orders"] = 0
        cust_dict["total_so"] = 0

    invoices = get_total_invoices_and_amount(cust_dict.name, from_date, to_date)
    if invoices:
        cust_dict["total_sales"] = flt(invoices[0]["total_net_amt"])
        cust_dict["total_invoices"] = flt(invoices[0]["invoices"])
    else:
        cust_dict["total_sales"] = 0
        cust_dict["total_invoices"] = 0
    factor, avg_monthly_orders = get_customer_rating_factor(cust_dict)
    cust_dict["factor"] = factor
    cust_dict["avg_monthly_orders"] = avg_monthly_orders
    cust_dict["total_rating"] = cust_dict["factor"] * cust_dict["pmt_factor"]
    return cust_dict