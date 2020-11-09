# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def execute():
    customers = frappe.db.sql("""SELECT name, customer_rating FROM `tabCustomer`""", as_dict=1)
    for cu in customers:
        print(f"Removing Customer Rating for {cu.name}")
        frappe.db.set_value("Customer", cu.name, "customer_rating", 0)
