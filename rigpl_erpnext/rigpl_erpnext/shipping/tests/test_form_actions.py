"""Shipment buttons of Carrier Tracking (#173)."""
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.rigpl_erpnext.shipping import form_actions as fa
from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.accounts import BOOKING, NONE, TRACKING_ONLY
from rigpl_erpnext.rigpl_erpnext.shipping.providers.dtdc import DTDC
from rigpl_erpnext.rigpl_erpnext.shipping.providers.fedex import FedEx
from rigpl_erpnext.rigpl_erpnext.shipping.providers.shipway import Shipway

from .test_dashboard import insert


def actions(docstatus=0, status="", has_awb=False, has_pod=False, posted=False, api_mode=BOOKING,
            caps=FedEx.capabilities, quote=False):
    return fa.allowed_actions(docstatus, status, has_awb, has_pod, posted, api_mode, caps, quote)


class TestAllowedActions(FrappeTestCase):
    def test_draft_not_booked_fedex(self):
        self.assertEqual(actions(), ["get_rates", "book_shipment", "address_validation", "available_services"])

    def test_after_cancel_can_book_again(self):
        self.assertIn("book_shipment", actions(status=st.NOT_BOOKED))

    def test_booked_shows_tracking_and_delete_only(self):
        self.assertEqual(actions(docstatus=1, status=st.BOOKED, has_awb=True), ["get_status", "delete_shipment"])
        self.assertEqual(actions(docstatus=1, status=st.BOOKED, has_awb=True, caps=DTDC.capabilities),
                         ["get_labels", "get_status", "delete_shipment"])

    def test_in_transit_cannot_book_rate_or_delete(self):
        self.assertEqual(actions(docstatus=1, status=st.IN_TRANSIT, has_awb=True), ["get_status"])
        self.assertEqual(actions(docstatus=1, status=st.IN_TRANSIT, has_awb=True, caps=DTDC.capabilities),
                         ["get_status"])  # no label after pickup

    def test_shipped_status_without_awb_is_not_bookable(self):
        self.assertEqual(actions(status=st.IN_TRANSIT), [])

    def test_pod_only_when_delivered_without_pod(self):
        self.assertEqual(actions(docstatus=1, status=st.DELIVERED, has_awb=True), ["get_pod"])
        self.assertEqual(actions(docstatus=1, status=st.DELIVERED, has_awb=True, has_pod=True), [])
        self.assertEqual(actions(docstatus=1, status=st.DELIVERED, has_awb=True, caps=DTDC.capabilities), [])

    def test_tracking_only_never_books_or_deletes(self):
        self.assertEqual(actions(api_mode=TRACKING_ONLY, caps=DTDC.capabilities), ["available_services"])
        self.assertEqual(actions(docstatus=1, status=st.BOOKED, has_awb=True, api_mode=TRACKING_ONLY,
                                 caps=DTDC.capabilities), ["get_labels", "get_status"])

    def test_rates_from_quote_without_rate_api(self):
        self.assertIn("get_rates", actions(api_mode=NONE, caps=frozenset(), quote=True))

    def test_shipway_push_once(self):
        self.assertEqual(actions(docstatus=1, status=st.IN_TRANSIT, has_awb=True, api_mode=TRACKING_ONLY,
                                 caps=Shipway.capabilities), ["get_status", "pushdata"])
        self.assertNotIn("pushdata", actions(docstatus=1, status=st.IN_TRANSIT, has_awb=True, posted=True,
                                             api_mode=TRACKING_ONLY, caps=Shipway.capabilities))

    def test_cancelled_document_has_no_actions(self):
        self.assertEqual(actions(docstatus=2, status=st.BOOKED, has_awb=True), [])


class TestCheckAction(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    @patch.object(fa, "transporter_api", return_value=("FedEx", BOOKING))
    def test_uses_saved_state_not_the_form_copy(self, _):
        insert("Transporters", "_Test RIGPL FA Air")
        insert("Carrier Tracking", "_Test RIGPL FA1", carrier_name="_Test RIGPL FA Air", status=st.IN_TRANSIT,
               awb_number="AWB1", docstatus=1)
        doc = frappe.get_doc("Carrier Tracking", "_Test RIGPL FA1")
        doc.status, doc.docstatus, doc.awb_number = st.NOT_BOOKED, 0, "NA"  # changed in the browser
        with self.assertRaises(frappe.ValidationError):
            fa.check_action(doc, "book_shipment")
        fa.check_action(doc, "get_status")

    def test_unsaved_doc_throws(self):
        doc = frappe.new_doc("Carrier Tracking")
        with self.assertRaises(frappe.ValidationError):
            fa.check_action(doc, "get_rates")
