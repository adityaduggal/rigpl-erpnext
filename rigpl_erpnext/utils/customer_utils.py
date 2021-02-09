# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
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


def get_contact(link_type, link_name):
    cont_list = frappe.db.sql("""SELECT con.name, con.is_primary_contact, con.accounts_related 
    FROM `tabContact` con, `tabDynamic Link` dl 
    WHERE dl.parent = con.name AND dl.parenttype = 'Contact' AND dl.link_doctype = '%s' 
    AND dl.link_name = '%s' ORDER BY con.is_primary_contact, con.accounts_related, 
    con.name""" % (link_type, link_name), as_dict=1)
    return cont_list


def return_email_verified_for_contact(contact_name):
    emails = frappe.db.sql("""SELECT email_id, is_primary, validated FROM `tabContact Email` 
    WHERE parenttype = 'Contact' AND parent = '%s'""" % contact_name, as_dict=1)
    if not emails:
        return 0
    else:
        for em in emails:
            if em.validated == 1:
                return 1
    return 0