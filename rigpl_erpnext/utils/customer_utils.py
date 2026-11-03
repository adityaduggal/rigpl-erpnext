# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
from __future__ import unicode_literals
import frappe


def disable_pricing_rule(cu_name):
    pr_rule = frappe.get_all("Pricing Rule", filters={"customer": cu_name}, fields=["name", "customer"])
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
    con = frappe.qb.DocType("Contact")
    dl = frappe.qb.DocType("Dynamic Link")
    return (
        frappe.qb.from_(con)
        .join(dl).on(dl.parent == con.name)
        .select(con.name, con.is_primary_contact, con.accounts_related)
        .where(dl.parenttype == "Contact")
        .where(dl.link_doctype == link_type)
        .where(dl.link_name == link_name)
        .orderby(con.is_primary_contact)
        .orderby(con.accounts_related)
        .orderby(con.name)
        .run(as_dict=True)
    )


def return_email_verified_for_contact(contact_name):
    validated = frappe.db.exists("Contact Email", {"parenttype": "Contact", "parent": contact_name,
        "validated": 1})
    return 1 if validated else 0