#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import division
import frappe
from ...utils.other_utils import validate_ifsc_code


def validate(doc, method):
    populate_account_name(doc)
    # Only One Bank Account per Party if Allow Multiple is Not Set
    if doc.is_company_account != 1:
        other_bank = frappe.db.sql("""SELECT name FROM `tabBank Account` WHERE party = '%s' AND party_type = '%s'
        AND allow_multiple != 1 AND name != '%s'""" % (doc.party, doc.party_type, doc.name), as_dict=1)
        if other_bank:
            frappe.throw(f"{frappe.get_desk_link('Bank Account', other_bank[0].name)} Already Exists.")

    if doc.bank:
        bank_ifsc = frappe.get_value("Bank", doc.bank, "bank_ifsc_code")
        if doc.branch_code[:len(bank_ifsc)] != bank_ifsc:
            frappe.throw(f"IFSC Code for {doc.name} should being with {bank_ifsc}")
        validate_ifsc_code(doc.branch_code)


def autoname(doc, method):
    populate_account_name(doc)
    doc.name = doc.account_name


def populate_account_name(doc):
    if doc.is_company_account == 1:
        doc.account_name = doc.bank_account_no + "-" + doc.bank
    else:
        doc.account_name = doc.party_type + ":" + doc.party + "-" + doc.bank_account_no