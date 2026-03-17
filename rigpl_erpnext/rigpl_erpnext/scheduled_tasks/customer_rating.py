# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
import datetime
from frappe.utils import add_days, flt
from ...utils.accounts_receivable_utils import get_average_payment_days, get_customer_pmt_factor
from ...utils.sales_utils import get_total_sales_orders, get_first_order, get_customer_rating_factor, \
    get_customer_rating_from_pts, get_total_company_sales, get_total_invoices_and_amount
from frappe.utils.background_jobs import enqueue


def execute():
    st_time = time.time()
    
    customers = frappe.db.sql("""SELECT name, customer_rating FROM `tabCustomer` ORDER BY name""", as_dict=1)
    
    # 1. Prepare global settings
    settings = frappe.get_cached_doc("RIGPL Settings", "RIGPL Settings")
    years = flt(settings.years_to_consider) or 5
    fov = flt(settings.minimum_first_order) or 10000
    days = years * 365
    to_date = datetime.datetime.today().date()
    from_date = add_days(to_date, days * (-1))
    
    # 2. Bulk fetch data for all active stuff
    tot_company_sales_sql = frappe.db.sql("""SELECT SUM(base_grand_total) FROM `tabSales Invoice`
        WHERE docstatus = 1 AND is_pos = 0 AND posting_date >= %s
        AND posting_date <= %s""", (from_date, to_date))
    tot_company_sales = tot_company_sales_sql[0][0] if tot_company_sales_sql and tot_company_sales_sql[0][0] else 0.0

    # Sales Orders
    so_data = frappe.db.sql("""SELECT customer, SUM(base_net_total) AS total_net_amt, COUNT(name) AS so
        FROM `tabSales Order` WHERE docstatus = 1 AND base_net_total > 0 AND transaction_date >= %s
        AND transaction_date <= %s GROUP BY customer""", (from_date, to_date), as_dict=1)
    so_map = {d.customer: {"total_orders": flt(d.total_net_amt), "total_so": flt(d.so)} for d in so_data}

    # Invoices and payments
    inv_data = frappe.db.sql("""SELECT customer, SUM(base_net_total) AS total_net_amt, COUNT(name) AS invoices
        FROM `tabSales Invoice` WHERE docstatus = 1 AND base_net_total > 0 AND posting_date >= %s
        AND posting_date <= %s GROUP BY customer""", (from_date, to_date), as_dict=1)
    inv_map = {d.customer: {"total_sales": flt(d.total_net_amt), "total_invoices": flt(d.invoices)} for d in inv_data}

    # First orders
    first_orders = frappe.db.sql("""SELECT customer, MIN(transaction_date) as date 
        FROM `tabSales Order` WHERE docstatus = 1 AND base_net_total > %s 
        GROUP BY customer""", (fov,), as_dict=1)
    first_order_map = {d.customer: d.date for d in first_orders}

    # Average payment days - Bulk
    all_inv = frappe.db.sql("""SELECT customer, name, base_net_total as net_amt,
        base_grand_total as grand_total, posting_date, due_date FROM `tabSales Invoice`
        WHERE docstatus = 1 AND base_grand_total > 0 AND is_pos = 0
        AND posting_date >= %s AND posting_date <= %s""", (from_date, to_date), as_dict=1)
    
    all_gl = frappe.db.sql("""SELECT against_voucher, posting_date, debit, credit, reference_type
            FROM `tabGL Entry` WHERE party_type="Customer" AND voucher_type in ('Journal Entry',
            'Payment Entry') AND against_voucher IS NOT NULL""", as_dict=1)
    
    gl_map = {}
    for d in all_gl:
        gl_map.setdefault(d.against_voucher, []).append(d)
        
    avg_pmt_days_map = {}
    inv_by_customer = {}
    for inv in all_inv:
        inv_by_customer.setdefault(inv.customer, []).append(inv)
        
    for customer, inv_list in inv_by_customer.items():
        for inv in inv_list:
            inv["total_pmt_days"] = 0
            inv["paid_amt"] = 0
            for d in gl_map.get(inv.name, []):
                if d.reference_type == "Purchase Invoice":
                    payment_amount = flt(d.debit) or -1 * flt(d.credit)
                else:
                    payment_amount = flt(d.credit) or -1 * flt(d.debit)
                payment_days = (d.posting_date - inv.posting_date).days
                inv["total_pmt_days"] += payment_days * payment_amount
                inv["paid_amt"] += payment_amount
        
        total_pmt_days, total_invoice_amt, total_paid = 0,0,0
        total_unpaid, total_unpaid_days = 0,0
        for inv in inv_list:
            unpaid_days = (datetime.datetime.now().date() - inv.posting_date).days
            unpaid_amt = inv.grand_total - inv.paid_amt
            total_invoice_amt += inv.grand_total
            total_paid += inv.paid_amt
            total_pmt_days += inv.total_pmt_days
            total_unpaid += inv.grand_total - inv.paid_amt
            total_unpaid_days += unpaid_days * unpaid_amt
        
        if (total_paid + total_unpaid) > 0:
            avg_pmt_days_map[customer] = int((total_pmt_days + total_unpaid_days) / (total_paid + total_unpaid))
        else:
            avg_pmt_days_map[customer] = 0

    customers_rated_list = []
    
    for cu in customers:
        cust_dict = dict(cu)
        customer = cust_dict["name"]
        
        cust_dict["avg_pmt_days"] = avg_pmt_days_map.get(customer, 0)
        cust_dict["pmt_factor"] = get_customer_pmt_factor(cust_dict)
        cust_dict["total_company_sales"] = tot_company_sales
        
        fo_date = first_order_map.get(customer, to_date)
        days_since = (to_date - fo_date).days
        cust_dict["period"] = days
        cust_dict["days_since"] = days_since
        
        so_data_cust = so_map.get(customer, {"total_orders": 0, "total_so": 0})
        cust_dict["total_orders"] = so_data_cust["total_orders"]
        cust_dict["total_so"] = so_data_cust["total_so"]
        
        inv_data_cust = inv_map.get(customer, {"total_sales": 0, "total_invoices": 0})
        cust_dict["total_sales"] = inv_data_cust["total_sales"]
        cust_dict["total_invoices"] = inv_data_cust["total_invoices"]
        
        age_wt = flt(settings.age_weightage)
        age_factor = min((days_since / (years*365))*100, 100)
        wt_age_factor = min(int(age_factor*(age_wt/100)), 100)
        cust_dict["age_factor"] = age_factor

        annual_base = flt(settings.base_annual_sales) or 100000
        sal_wt = flt(settings.sales_weightage)
        tot_sales = cust_dict["total_sales"]
        # The period in get_customer_rating_factor was basically 'days' 
        sales_factor = min(int(tot_sales*365*100/annual_base/days), 100)
        wt_sales_factor = int(sales_factor * (sal_wt/100))
        cust_dict["sales_factor"] = sales_factor

        pmt_wt = flt(settings.payment_weightage)
        pmt_factor = cust_dict["pmt_factor"] * 10
        wt_pmt_factor = int(pmt_factor * (pmt_wt / 100))
        cust_dict["pmt_factor"] = pmt_factor

        min_monthly_orders = flt(settings.minimum_orders_per_month)
        no_of_orders = cust_dict["total_so"]
        monthly_orders = int(no_of_orders * 365 / days / 12)
        cust_dict["avg_monthly_orders"] = monthly_orders
        
        if monthly_orders < min_monthly_orders and min_monthly_orders > 0:
            monthly_orders = min_monthly_orders

        if no_of_orders == 0:
            factor = 0
        else:
            if min_monthly_orders > 0:
                factor = wt_sales_factor + wt_age_factor + wt_pmt_factor - (min_monthly_orders/10)
            else:
                factor = wt_sales_factor + wt_age_factor + wt_pmt_factor
                
        cust_dict["total_rating"] = factor
        cust_dict["new_customer_rating"] = get_customer_rating_from_pts(cust_dict["total_rating"])
        
        customers_rated_list.append(cust_dict)
        
    customers_rated_list = sorted(customers_rated_list, key=lambda i:(i["total_rating"]), reverse=True)

    BATCH_SIZE = 500
    updated_count = 0
    
    for cu in customers_rated_list:
        # Safe string/float comparison depending on your data type
        old_rating = str(cu.get("customer_rating") or "")
        new_rating = str(cu["new_customer_rating"])
        
        if old_rating != new_rating:
            try:
                # db_set is 100x faster than frappe.get_doc().save()
                frappe.db.set_value("Customer", cu["name"], "customer_rating", cu["new_customer_rating"])
                updated_count += 1
                
                if updated_count % BATCH_SIZE == 0:
                    frappe.db.commit()
                    
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Rating update failed for {cu['name']}")

    frappe.db.commit() # Final commit for the remaining batch

    end_time = time.time()
    tot_time = round(end_time - st_time)
    frappe.logger("customer_rating").info(f"Updated {updated_count} customers in {tot_time} seconds")
    print(f"Total Time {tot_time} seconds")

def build_customer_rating(cust_dict, from_date=None, to_date=None, fov=None, days=None):
    if not days:
        years = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "years_to_consider"))
    else:
        years = days/365
    if years == 0:
        years = 5
    if not fov:
        fov = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "minimum_first_order"))
    if fov == 0:
        fov = 10000
    if not days:
        days = years * 365
    if not to_date:
        to_date = datetime.datetime.today().date()
    if not from_date:
        from_date = add_days(to_date, days*(-1))
    cust_dict["avg_pmt_days"] = get_average_payment_days(cust_dict.name, from_date, to_date)
    cust_dict["pmt_factor"] = get_customer_pmt_factor(cust_dict)
    cust_dict["total_company_sales"] = get_total_company_sales(from_date, to_date)
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
    get_customer_rating_factor(cust_dict, years)
    cust_dict["customer_rating"] = get_customer_rating_from_pts(cust_dict["total_rating"])
    return cust_dict
