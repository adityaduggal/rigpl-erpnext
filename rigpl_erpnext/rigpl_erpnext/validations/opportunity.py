# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
    # Check if Lead is Converted or Not, if the lead is converted
    # then don't allow it to be selected without linked customer
    if doc.opportunity_from == "Lead" and doc.party_name:
        customer = frappe.db.get_value("Customer", {"lead_name": doc.party_name})
        if customer:
            frappe.throw(("Lead {0} is Linked to Customer {1} so kindly make Opportunity for Customer "
                          "and not Lead").format(doc.party_name, customer))
