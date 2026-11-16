# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from erpnext.crm.doctype.lead.lead import Lead
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


class RigplLead(Lead):
    """Makes the Lead's Address and Contact after insert, already linked to the Lead.
    ERPNext makes them unlinked in before_insert, which rohit_common refuses."""

    def before_insert(self):
        pass

    def after_insert(self):
        lead_link = {"link_doctype": "Lead", "link_name": self.name, "link_title": self.lead_name}
        if self.address_title and self.address_type:
            self.address_doc = self.create_address(lead_link)
        self.contact_doc = self.create_contact(lead_link)

    def create_address(self, lead_link=None):
        # Field map from erpnext/crm/doctype/lead/lead.py:138-160
        address_fields = ["address_type", "address_title", "address_line1", "address_line2", "city",
                          "county", "state", "country", "pincode", "email_id", "phone", "fax"]
        address = frappe.new_doc("Address")
        address.update({field: self.get(field) for field in address_fields})
        # Lead has no GSTIN field; correct the Address before invoicing a Customer made from this Lead
        address.gstin = "NA"
        if self.state and frappe.db.exists("State", self.state):
            address.state_rigpl = self.state
        if lead_link:
            address.append("links", lead_link)
        address.insert(ignore_permissions=True)
        return address

    def create_contact(self, lead_link=None):
        # Field map from erpnext/crm/doctype/lead/lead.py:162-195
        if not self.lead_name:
            self.set_lead_name()
        first_name, _, last_name = self.lead_name.strip().partition(" ")
        contact = frappe.new_doc("Contact")
        contact.update({"first_name": first_name, "last_name": last_name or None,
                        "salutation": self.salutation, "gender": self.gender,
                        "designation": self.designation, "company_name": self.company_name})
        if self.email_id:
            contact.append("email_ids", {"email_id": self.email_id, "is_primary": 1})
        # rohit_common phone checks need a country, and a Lead without an Address has none to guess from
        country = self.country or frappe.db.get_default("country")
        if self.phone:
            contact.append("phone_nos", {"phone": self.phone, "is_primary_phone": 1, "country": country})
        if self.mobile_no:
            contact.append("phone_nos", {"phone": self.mobile_no, "is_primary_mobile_no": 1,
                                         "country": country})
        if lead_link:
            contact.append("links", lead_link)
        contact.insert(ignore_permissions=True)
        return contact
