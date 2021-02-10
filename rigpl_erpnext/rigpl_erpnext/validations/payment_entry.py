#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from operator import itemgetter
from ...utils.customer_utils import get_contact, return_email_verified_for_contact


def validate(doc, method):
    update_contact(doc)
    update_comp_bank_account(doc)
    if doc.payment_type == "Pay":
        update_party_bank_account(doc)


def on_submit(doc, method):
    if doc.no_validated_email != 1:
        if return_email_verified_for_contact(doc.contact_person) != 1:
            frappe.throw(f"{frappe.get_desk_link('Contact', doc.contact_person)} Does not Have a Validated Email. "
                         f"Either Validate Contact Email or if there is No Email for {doc.party_type}:{doc.party} "
                         f"then Check No Validate Email Check Box")


def update_contact(doc):
    if doc.payment_type in ("Pay", "Receive"):
        cont_list = get_contact(link_type=doc.party_type, link_name=doc.party)
        if not doc.contact_person:
            if cont_list:
                for con in cont_list:
                    valid_email = return_email_verified_for_contact(con.name)
                    con["email_validated"] = valid_email
                cont_list = sorted(cont_list, key=lambda i: (-i["email_validated"], -i["accounts_related"],
                                                             -i["is_primary_contact"], i["name"]))
                doc.contact_person = cont_list[0].name
                doc.email = ""
            else:
                frappe.throw(f"No Contact Found for {doc.party_type}:{doc.party}")


def update_party_bank_account(doc):
    ba = frappe.db.sql("""SELECT name, is_default FROM `tabBank Account` WHERE verified = 1 
    AND is_company_account = 0 AND party_type = '%s' AND party = '%s'""" % (doc.party_type, doc.party), as_dict=1)
    if ba:
        doc.party_bank_account = ba[0].name
    else:
        doc.party_bank_account = ""


def update_comp_bank_account(doc):
    if doc.payment_type == "Pay":
        account = doc.paid_from
    else:
        account = doc.paid_to
    query = """SELECT name FROM `tabBank Account` WHERE verified = 1 AND is_company_account = 1 AND account = 
    '%s'""" % account
    ba = frappe.db.sql(query, as_dict=1)
    if ba:
        doc.bank_account = ba[0].name
    else:
        doc.bank_account = ""
