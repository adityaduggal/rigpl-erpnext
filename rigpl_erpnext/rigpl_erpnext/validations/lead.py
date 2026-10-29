# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from rigpl_erpnext.utils.lead_share_utils import sync_lead_shares
from rohit_common.utils.email_utils import comma_email_validations


def validate(doc, method):
    """
    Does various validations for Lead Doctype
    1. Email ID is validated else removed
    """
    if doc.flags.ignore_mandatory == 1:
        backend = 1
    else:
        backend = 0
        if not doc.email_id:
            frappe.throw(f"For {frappe.get_desk_link('Lead', doc.name)} Email ID is Mandatory")
    doc.email_id = comma_email_validations(doc.email_id, backend=backend)
    if doc.lead_owner:
        if doc.lead_owner != doc.contact_by:
            doc.contact_by = doc.lead_owner


def on_update(doc, method):
    # Lock Lead if its linked to a Customer so no editing on Lead is allowed
    check_conversion = frappe.db.sql("""SELECT name FROM `tabCustomer`
    WHERE lead_name = %s""", doc.name, as_list=1)

    if check_conversion:
        frappe.throw(("Editing of Lead {0} NOT ALLOWED since its linked to Customer {1}. Kindly add information "
                      "to Customer Master and not Lead").format(doc.name, check_conversion[0][0]))
    sync_lead_shares([doc.name])
