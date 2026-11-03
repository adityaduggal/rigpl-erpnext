"""
CRM and Selling validations after the move from '%s' SQL to parameters (#187). Each name has a
quote: the old code put it into the SQL text and failed.
"""
from types import SimpleNamespace

import frappe

from rigpl_erpnext.rigpl_erpnext.doctype.daily_call.daily_call import check_contact
from rigpl_erpnext.rigpl_erpnext.validations import customer as customer_validation
from rigpl_erpnext.rigpl_erpnext.validations import opportunity as opportunity_validation
from rigpl_erpnext.selling_rigpl.validations.sales_order import delete_process_sheet, get_trial_tracking
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw
from rigpl_erpnext.utils.accounts_receivable_utils import get_overdue_si
from rigpl_erpnext.utils.customer_utils import get_contact, return_email_verified_for_contact

CUSTOMER = "_Test RIGPL O'Brien CRM Customer"
OTHER_CUSTOMER = "_Test RIGPL O'Brien CRM Customer 2"
LEAD = "_Test RIGPL O'Lead"
SO = "_Test RIGPL O'SO"
MTO_ITEM = "_Test RIGPL O'MTO Item"
STOCK_ITEM = "_Test RIGPL O'Stock Item"


def insert_contact(name, customer, primary=0, accounts=0):
    raw("Contact", name=name, first_name=name, is_primary_contact=primary, accounts_related=accounts)
    raw("Dynamic Link", parent=name, parenttype="Contact", parentfield="links", link_doctype="Customer",
        link_name=customer)


class TestCustomerChecks(ReportTestCase):
    def test_duplicate_login_id_and_lead(self):
        raw("Customer", name=OTHER_CUSTOMER, customer_name=OTHER_CUSTOMER, customer_login_id="o'brien@test",
            lead_name=LEAD)

        login = frappe._dict(name=CUSTOMER, customer_login_id="o'brien@test")
        self.assertRaisesRegex(frappe.ValidationError, "already linked to User ID",
            customer_validation.on_update, login, "on_update")
        lead = frappe._dict(name=CUSTOMER, lead_name=LEAD)
        self.assertRaisesRegex(frappe.ValidationError, "already linked to Customer",
            customer_validation.on_update, lead, "on_update")


class TestOpportunityCheck(ReportTestCase):
    def test_lead_linked_to_customer(self):
        raw("Customer", name=CUSTOMER, customer_name=CUSTOMER, lead_name=LEAD)

        doc = frappe._dict(opportunity_from="Lead", party_name=LEAD)
        self.assertRaisesRegex(frappe.ValidationError, "make Opportunity for Customer",
            opportunity_validation.validate, doc, "validate")
        opportunity_validation.validate(frappe._dict(opportunity_from="Lead", party_name="O'Free Lead"), "validate")
        opportunity_validation.validate(frappe._dict(opportunity_from="Customer", party_name=CUSTOMER), "validate")


class TestDailyCallContact(ReportTestCase):
    def test_contacts_of_the_link(self):
        insert_contact("_Test RIGPL O'Contact", CUSTOMER)
        insert_contact("_Test RIGPL O'Other Contact", OTHER_CUSTOMER)

        self.assertEqual(check_contact("Customer", CUSTOMER), [["_Test RIGPL O'Contact"]])
        check_contact("Customer", CUSTOMER, "_Test RIGPL O'Contact")
        self.assertRaises(frappe.ValidationError, check_contact, "Customer", CUSTOMER, "_Test RIGPL O'Other Contact")


class TestCustomerUtils(ReportTestCase):
    def test_contact_order_and_validated_email(self):
        insert_contact("_Test RIGPL O'Contact B", CUSTOMER, primary=1)
        insert_contact("_Test RIGPL O'Contact A", CUSTOMER, accounts=1)
        insert_contact("_Test RIGPL O'Contact C", CUSTOMER)
        raw("Contact Email", parent="_Test RIGPL O'Contact A", parenttype="Contact", parentfield="email_ids",
            email_id="a@test", validated=0)
        raw("Contact Email", parent="_Test RIGPL O'Contact B", parenttype="Contact", parentfield="email_ids",
            email_id="b@test", validated=1)

        rows = get_contact("Customer", CUSTOMER)

        self.assertEqual([row.name for row in rows],
            ["_Test RIGPL O'Contact C", "_Test RIGPL O'Contact A", "_Test RIGPL O'Contact B"])
        self.assertEqual(return_email_verified_for_contact("_Test RIGPL O'Contact A"), 0)
        self.assertEqual(return_email_verified_for_contact("_Test RIGPL O'Contact B"), 1)
        self.assertEqual(return_email_verified_for_contact("_Test RIGPL O'Contact C"), 0)

    def test_overdue_invoices_oldest_first(self):
        new = raw("Sales Invoice", customer=CUSTOMER, docstatus=1, outstanding_amount=100, posting_date="2026-02-01")
        old = raw("Sales Invoice", customer=CUSTOMER, docstatus=1, outstanding_amount=50, posting_date="2026-01-01")
        raw("Sales Invoice", customer=CUSTOMER, docstatus=1, outstanding_amount=0, posting_date="2026-01-01")
        raw("Sales Invoice", customer=CUSTOMER, docstatus=0, outstanding_amount=10, posting_date="2026-01-01")

        self.assertEqual([si.name for si in get_overdue_si(CUSTOMER)], [old, new])


class TestSalesOrderCancel(ReportTestCase):
    def test_draft_process_sheets_of_mto_items_are_deleted(self):
        raw("Item", name=MTO_ITEM, item_code=MTO_ITEM, item_name=MTO_ITEM, made_to_order=1, stock_uom="Nos")
        raw("Item", name=STOCK_ITEM, item_code=STOCK_ITEM, item_name=STOCK_ITEM, made_to_order=0, stock_uom="Nos")
        # A frappe._dict has the dict method items, so the SO is a namespace
        so = SimpleNamespace(name=SO, items=[
            frappe._dict(name="O'SOI-1", item_code=MTO_ITEM),
            frappe._dict(name="O'SOI-2", item_code=STOCK_ITEM),
        ])
        draft = raw("Process Sheet", sales_order=SO, sales_order_item="O'SOI-1", docstatus=0)
        submitted = raw("Process Sheet", sales_order=SO, sales_order_item="O'SOI-1", docstatus=1)
        stock = raw("Process Sheet", sales_order=SO, sales_order_item="O'SOI-2", docstatus=0)

        delete_process_sheet(so)

        self.assertFalse(frappe.db.exists("Process Sheet", draft))
        self.assertTrue(frappe.db.exists("Process Sheet", submitted))
        self.assertTrue(frappe.db.exists("Process Sheet", stock))

    def test_first_trial_tracking_per_so_item(self):
        first = raw("Trial Tracking", prevdoc_detail_docname="O'SOI-1", creation="2026-01-01")
        raw("Trial Tracking", prevdoc_detail_docname="O'SOI-1", creation="2026-01-02")
        other = raw("Trial Tracking", prevdoc_detail_docname="O'SOI-2", creation="2026-01-01")

        trials = self.assert_queries(1, lambda: get_trial_tracking(["O'SOI-1", "O'SOI-2", "O'SOI-3"]))

        self.assertEqual(trials, {"O'SOI-1": first, "O'SOI-2": other})
