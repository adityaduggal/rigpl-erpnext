# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt
# This file is to automate things based on customer rating this should run ideally every month
# Pricing Rule Automations Like Disable Pricing Rules for ZERO Rated Customers
# Check the Payment Terms for Zero Rated Customers
from __future__ import unicode_literals
import frappe
from ...utils.customer_utils import disable_pricing_rule


def execute():
    cust_list = frappe.db.sql("""SELECT name, customer_rating FROM `tabCustomer` 
    ORDER BY customer_rating, name""", as_dict=1)
    for cu in cust_list:
        print(f"Checking for Customer: {cu.name} with Rating: {cu.customer_rating}")
        cu_doc = frappe.get_doc("Customer", cu.name)
        if cu_doc.customer_rating == 0:
            # Customer Rating = 0 Disable Pricing Rule, Set Payment Terms to ZERO Days and Strict
            disable_pricing_rule(cu.name)
