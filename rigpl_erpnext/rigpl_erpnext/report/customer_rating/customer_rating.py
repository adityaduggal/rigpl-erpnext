# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import getdate, add_days
from ...scheduled_tasks.customer_rating import build_customer_ratings
from ....utils.report_utils import tree_and_descendants

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    return [
            "Customer:Link/Customer:200", "Territory:Link/Territory:150",
            "Group:Link/Customer Group:100",
            "Payment Terms:Link/Payment Terms Template:100", "Avg Credit as per Terms:Int:60",
            "Pmt SF Requirement:Int:60",
            "Avg Pmt Days:Int:50", "Diff:Int:60", "PF:Int:50", "AF:Int:50",
            "SF:Int:50", "SF Diff:Int:50", "Period:Int:50", "Since:Int:50",
            "Total SO:Currency:100", "# SO:Int:80", "Total Sales:Currency:100",
            "# SI:Int:50", "Total Rating:Int:100", "# Monthly Orders:Int:50",
            "Calculated Rating:Int:80", "Actual Rating:Int:80", "Difference:Int:80"
    ]

def get_data(filters):
    to_date = getdate(filters.get("to_date"))
    years = filters.get("years")
    from_date = add_days(to_date, years*(-365))
    period = (to_date - from_date).days
    fov = filters.get("first_order")
    cust_list = get_customers(filters)
    customers_rated = build_customer_ratings(cust_list, from_date=from_date, to_date=to_date,
        fov=fov, days=years*365)
    for cust_dict in customers_rated:
        cust_dict["period"] = period
    customers_rated = sorted(customers_rated, key=lambda i: (i["total_rating"]))
    pmt_terms_dict = {pt.name: pt for pt in frappe.get_all("Payment Terms Template",
        fields=["name", "average_credit_days", "minimum_sales_rating"])}
    data = []
    for cu in customers_rated:
        if cu.payment_terms:
            pmt_doc = pmt_terms_dict[cu.payment_terms]
            pmt_days = pmt_doc.average_credit_days
            sales_rating = pmt_doc.minimum_sales_rating
            pmt_terms = cu.payment_terms
        else:
            pmt_days = 0
            sales_rating = 0
            pmt_terms = "No Payment Terms"
        row = [
            cu.name, cu.territory, cu.customer_group, pmt_terms, pmt_days, sales_rating,
            cu.avg_pmt_days, (pmt_days - cu.avg_pmt_days), cu.pmt_factor, cu.age_factor,
            cu.sales_factor, (cu.sales_factor - sales_rating), cu.period, cu.days_since,
            cu.total_orders, cu.total_so, cu.total_sales,
            cu.total_invoices, cu.total_rating, cu.avg_monthly_orders, cu.customer_rating,
            cu.actual_rating, (cu.customer_rating - cu.actual_rating)
        ]
        data.append(row)
    # data = sorted(data, key=lambda i:(i["total_rating"]))
    return data


def get_customers(filters):
    cu = frappe.qb.DocType("Customer")
    query = (
        frappe.qb.from_(cu)
        .select(cu.name, cu.territory, cu.customer_group, cu.payment_terms, cu.customer_rating.as_("actual_rating"))
        .where(cu.docstatus == 0)
    )
    if filters.get("customer"):
        query = query.where(cu.name == filters["customer"])
    if filters.get("territory"):
        query = query.where(cu.territory.isin(tree_and_descendants("Territory", filters["territory"])))
    # The JS filter is "group"
    customer_group = filters.get("group") or filters.get("customer_group")
    if customer_group:
        query = query.where(cu.customer_group.isin(tree_and_descendants("Customer Group", customer_group)))
    return query.run(as_dict=1)

