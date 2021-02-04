#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
    if doc.payment_type == "Pay":
        update_comp_bank_account(doc)
        update_party_bank_account(doc)


def update_party_bank_account(doc):
    ba = frappe.db.sql("""SELECT name, is_default FROM `tabBank Account` WHERE verified = 1 
    AND is_company_account = 0 AND party_type = '%s' AND party = '%s'""" % (doc.party_type, doc.party), as_dict=1)
    if ba:
        doc.party_bank_account = ba[0].name
    else:
        doc.party_bank_account = ""


def update_comp_bank_account(doc):
    ba = frappe.db.sql("""SELECT name FROM `tabBank Account` WHERE verified = 1 AND is_company_account = 1 
    AND account = '%s'""" % doc.paid_from, as_dict=1)
    if ba:
        doc.bank_account = ba[0].name
    else:
        doc.bank_account = ""
