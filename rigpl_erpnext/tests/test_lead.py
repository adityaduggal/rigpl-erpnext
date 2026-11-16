"""
A new Lead makes its Contact and Address already linked to the Lead, so rohit_common does not refuse
them as orphans. A Sales Representative with no create right on Contact can still save a Lead.
"""
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.tests.test_lead_share import ensure_share_rule
from rigpl_erpnext.tests.test_selling_reports import raw

EMAIL = "_test_rigpl_lead@example.com"
REP = "_test_rigpl_lead_rep@example.com"


class TestLead(FrappeTestCase):
    def setUp(self):
        raw("Global Emails", name=EMAIL, email_id=EMAIL)
        # The ERPNext Call Log hook on Contact commits once per phone number
        for target in (patch.object(frappe.db, "commit"),
                       patch("rohit_common.rohit_common.validations.address.check_need_for_geocode")):
            target.start()
            self.addCleanup(target.stop)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def make_lead(self, **values):
        lead = frappe.get_doc(dict(doctype="Lead", lead_name="_Test RIGPL Lead", company_name="_Test RIGPL Co",
                                   email_id=EMAIL, mobile_no="9876543210", requirement=1,
                                   territory=frappe.get_all("Territory", {"is_group": 0}, pluck="name", limit=1)[0],
                                   country="India", **values))
        lead.insert()
        return lead

    def linked(self, doctype, lead):
        return frappe.get_all("Dynamic Link", filters={"parenttype": doctype, "link_doctype": "Lead",
                                                       "link_name": lead.name}, pluck="parent")

    def test_contact_is_linked_to_lead(self):
        lead = self.make_lead()
        contacts = self.linked("Contact", lead)
        self.assertEqual(len(contacts), 1)
        self.assertEqual(len(frappe.get_doc("Contact", contacts[0]).links), 1)
        self.assertFalse(self.linked("Address", lead))

    def test_address_is_linked_to_lead(self):
        lead = self.make_lead(address_title="_Test RIGPL Lead", address_type="Billing", address_line1="Plot 1",
                              city="Gurugram", state="Haryana", pincode="122001")
        addresses = self.linked("Address", lead)
        self.assertEqual(len(addresses), 1)
        address = frappe.get_doc("Address", addresses[0])
        self.assertEqual(address.state_rigpl, "Haryana")
        self.assertEqual(address.gstin, "NA")
        self.assertEqual(len(address.links), 1)
        self.assertEqual(len(self.linked("Contact", lead)), 1)

    def test_sales_representative_can_make_lead(self):
        raw("User", name=REP, email=REP, first_name="_Test RIGPL Lead Rep", user_type="System User", enabled=1)
        raw("Has Role", parent=REP, parenttype="User", parentfield="roles", role="Sales Representative")
        # Reps have User Permissions on Contact and Address for their Customers, so only a share opens new ones
        ensure_share_rule("Address")
        for doctype in ("Contact", "Address"):
            raw("User Permission", user=REP, allow=doctype, for_value="_Test RIGPL Other " + doctype,
                apply_to_all_doctypes=1)
        frappe.clear_cache(user=REP)
        self.assertFalse(frappe.has_permission("Contact", "create", user=REP))
        frappe.set_user(REP)
        lead = self.make_lead(lead_owner=REP, address_title="_Test RIGPL Lead", address_type="Billing",
                              address_line1="Plot 1", city="Gurugram", state="Haryana", pincode="122001")
        frappe.set_user("Administrator")
        for doctype in ("Contact", "Address"):
            names = self.linked(doctype, lead)
            self.assertEqual(len(names), 1)
            self.assertTrue(frappe.has_permission(doctype, "read", names[0], user=REP), doctype)
