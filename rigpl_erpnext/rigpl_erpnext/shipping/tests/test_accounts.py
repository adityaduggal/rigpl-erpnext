import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.rigpl_erpnext.shipping.accounts import (
    BOOKING,
    NONE,
    TRACKING_ONLY,
    account_name,
    plan_accounts,
    provider_and_mode,
)

SHIPWAY = {"username": "sw-user", "license_key": "sw-key"}


def dtdc(name, service, **kw):
    row = dict(name=name, dtdc_credentials=1, dtdc_service_id=service, api_key="k1", dtdc_customer_code="C1",
               dtdc_tracking_username="u", dtdc_tracking_password="p")
    row.update(kw)
    return row


def fedex(name, account, service, **kw):
    row = dict(name=name, fedex_credentials=1, fedex_account_number=account, fedex_service_code=service)
    row.update(kw)
    return row


class TestShippingAccounts(FrappeTestCase):
    def test_mode_from_the_old_checkboxes(self):
        self.assertEqual(provider_and_mode({"fedex_credentials": 1}), ("FedEx", BOOKING))
        self.assertEqual(provider_and_mode({"fedex_tracking_only": 1}), ("FedEx", TRACKING_ONLY))
        self.assertEqual(provider_and_mode({"dtdc_credentials": 1}), ("DTDC", BOOKING))
        self.assertEqual(provider_and_mode({"dtdc_tracking_only": 1}), ("DTDC", TRACKING_ONLY))
        self.assertEqual(provider_and_mode({"track_on_shipway": 1}), ("Shipway", TRACKING_ONLY))
        self.assertEqual(provider_and_mode({"self_pickup": 1}), (None, NONE))

    def test_same_credentials_share_one_account(self):
        rows = [
            dtdc("DTDC Air", "PRIORITY"),
            dtdc("DTDC Ground", "SURFACE EXPRESS", dtdc_credentials=0, dtdc_tracking_only=1),
            fedex("FedEx Export", "111", "INTERNATIONAL_PRIORITY"),
            fedex("FedEx Export Eco", "111", "INTERNATIONAL_ECONOMY"),
            fedex("FedEx Domestic", "222", "STANDARD_OVERNIGHT"),
            dict(name="Speed Post", track_on_shipway=1, shipway_id=12),
            dict(name="Self", self_pickup=1),
        ]
        accounts, links = plan_accounts(rows, SHIPWAY, taken=set())

        self.assertEqual(sorted(accounts), ["DTDC C1", "FedEx 111", "FedEx 222", "Shipway"])
        self.assertEqual(accounts["DTDC C1"]["api_key"], "k1")
        self.assertEqual(accounts["Shipway"]["password"], "sw-key")
        self.assertNotIn("Self", links)
        self.assertEqual(links["DTDC Ground"], {
            "shipping_provider_account": "DTDC C1", "api_mode": TRACKING_ONLY, "provider_service_code": "SURFACE EXPRESS",
        })
        self.assertEqual(links["FedEx Export Eco"]["shipping_provider_account"], "FedEx 111")
        self.assertEqual(links["Speed Post"]["provider_service_code"], "12")

    def test_fedex_soap_secrets_are_not_copied(self):
        accounts, _ = plan_accounts([fedex("F", "111", "X", api_key="soap-key")], SHIPWAY, taken=set())
        self.assertNotIn("soap-key", accounts["FedEx 111"].values())

    def test_linked_transporters_are_skipped_on_a_second_run(self):
        row = dtdc("DTDC Air", "PRIORITY", shipping_provider_account="DTDC C1")
        self.assertEqual(plan_accounts([row], SHIPWAY, taken={"DTDC C1"}), ({}, {}))

    def test_a_taken_name_gets_a_number(self):
        self.assertEqual(account_name("DTDC", {"customer_code": "C1"}, {"DTDC C1"}), "DTDC C1 2")
        self.assertEqual(account_name("Shipway", {}, set()), "Shipway")


class TestAccountForm(FrappeTestCase):
    """A save keeps only the fields of the provider, and deletes the other stored secrets."""

    def tearDown(self):
        frappe.db.rollback()

    def test_save_clears_the_fields_of_other_providers(self):
        doc = frappe.get_doc(dict(doctype="Shipping Provider Account", account_name="_Test RIGPL Form", provider="DTDC",
                                  enabled=1, customer_code="C1", api_key="dtdc-key", username="u", password="p",
                                  tracking_base_url="https://t.example", is_sandbox=1, webhook_enabled=1)).insert()
        self.assertEqual((doc.is_sandbox, doc.webhook_enabled), (0, 1))
        self.assertEqual(doc.get_password("api_key"), "dtdc-key")

        doc.update(dict(provider="FedEx", account_number="111", client_id="id", client_secret="secret", is_sandbox=1))
        doc.save()
        doc.reload()
        self.assertEqual((doc.customer_code, doc.username, doc.tracking_base_url), (None, None, None))
        self.assertEqual((doc.account_number, doc.client_id, doc.is_sandbox, doc.webhook_enabled), ("111", "id", 1, 1))
        self.assertEqual(doc.get_password("client_secret"), "secret")
        stored = [r[0] for r in frappe.db.sql("SELECT fieldname FROM `__Auth` WHERE doctype = %s AND name = %s",
                                              (doc.doctype, doc.name))]
        self.assertEqual(sorted(stored), ["client_secret"])

        doc.update(dict(provider="Shipway", username="sw", password="sw-key"))
        doc.save()
        doc.reload()
        self.assertEqual((doc.account_number, doc.client_id, doc.is_sandbox, doc.webhook_enabled), (None, None, 0, 0))

    def test_fedex_needs_the_rest_keys(self):
        doc = frappe.get_doc(dict(doctype="Shipping Provider Account", account_name="_Test RIGPL Form 2",
                                  provider="FedEx", enabled=1, account_number="111"))
        with self.assertRaises(frappe.MandatoryError):
            doc.insert()
