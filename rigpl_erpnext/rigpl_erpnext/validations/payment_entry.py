#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from operator import itemgetter
from ...utils.customer_utils import get_contact, return_email_verified_for_contact


def validate(doc, method):
    set_employment_type_from_user_permission(doc)
    update_contact(doc)
    update_comp_bank_account(doc)
    if doc.payment_type == "Pay":
        update_party_bank_account(doc)


def before_insert(doc, method):
    """Set ignore_permlevel_for_fields flag before validate_higher_perm_levels runs.

    During insert, the flow is: before_insert → validate_higher_perm_levels → validate.
    The employment_type field (permlevel=1, mandatory) gets auto-filled from User Permission,
    but validate_higher_perm_levels strips it for users without write access at permlevel 1.
    This flag tells Frappe to skip the permlevel check for this specific field.
    """
    doc.flags.ignore_permlevel_for_fields = doc.flags.get(
        "ignore_permlevel_for_fields", []
    )
    if "employment_type" not in doc.flags.ignore_permlevel_for_fields:
        doc.flags.ignore_permlevel_for_fields.append("employment_type")


def set_employment_type_from_user_permission(doc):
    """Auto-fill employment_type from User Permission if it's empty.

    This acts as a safety net: if the employment_type field was stripped by
    validate_higher_perm_levels (e.g. during save/update), or if it was not
    sent by the client, this re-fills it from the user's User Permission.
    """
    if not doc.employment_type:
        user_perms = frappe.permissions.get_user_permissions(frappe.session.user)
        et_perms = user_perms.get("Employment Type", [])
        if et_perms:
            doc.employment_type = et_perms[0].get("doc")



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
        if not doc.party_bank_account:
            doc.party_bank_account = ba[0].name
        else:
            found = 0
            for d in ba:
                if doc.party_bank_account == d.name:
                    found = 1
            if found != 1:
                frappe.throw(f"{d.party_bank_account} Selected is Not a Verified Bank Account in {doc.name}")
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
