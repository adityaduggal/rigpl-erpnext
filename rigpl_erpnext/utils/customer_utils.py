# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe


def disable_pricing_rule(cu_name):
    pr_rule = frappe.db.sql("""SELECT name, customer FROM `tabPricing Rule` 
    WHERE customer ='%s'""" %(cu_name), as_dict=1)
    for pr in pr_rule:
        prd = frappe.get_doc("Pricing Rule", pr.name)
        prd.disable = 1
        try:
            prd.save()
            print(f"Disabled {pr.name} for Customer: {cu_name}")
        except:
            frappe.db.set_value("Pricing Rule", pr.name, "disable", 1)
            print(f"Disabled {pr.name} for Customer: {cu_name} without Saving")
