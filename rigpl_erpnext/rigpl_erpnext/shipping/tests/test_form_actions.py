"""Shipment buttons of Carrier Tracking (#173)."""
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.rigpl_erpnext.shipping import actions as shipping_actions
from rigpl_erpnext.rigpl_erpnext.shipping import form_actions as fa
from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.accounts import BOOKING, NONE, TRACKING_ONLY
from rigpl_erpnext.rigpl_erpnext.shipping.base import BookingResult, ProviderError
from rigpl_erpnext.rigpl_erpnext.shipping.providers.dtdc import DTDC
from rigpl_erpnext.rigpl_erpnext.shipping.providers.fedex import FedEx
from rigpl_erpnext.rigpl_erpnext.shipping.providers.shipway import Shipway

from .test_dashboard import insert


def actions(docstatus=0, status="", has_awb=False, has_pod=False, posted=False, api_mode=BOOKING,
            caps=FedEx.capabilities, quote=False, preview=False):
    return fa.allowed_actions(docstatus, status, has_awb, has_pod, posted, api_mode, caps, quote, preview)


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
        self.assertEqual(actions(docstatus=2, status=st.BOOKED, has_awb=True, preview=True), [])

    def test_preview_request_is_last_and_only_for_the_allowed_user_and_a_provider_that_has_it(self):
        self.assertNotIn("preview_request", actions())
        self.assertEqual(actions(preview=True)[-1], "preview_request")
        self.assertEqual(actions(docstatus=1, status=st.BOOKED, has_awb=True, preview=True),
                         ["get_status", "delete_shipment", "preview_request"])  # any status
        self.assertIn("preview_request", actions(docstatus=1, status=st.DELIVERED, has_awb=True, preview=True))
        self.assertIn("preview_request", actions(api_mode=TRACKING_ONLY, caps=DTDC.capabilities, preview=True))
        self.assertNotIn("preview_request", actions(api_mode=NONE, preview=True))
        self.assertNotIn("preview_request", actions(caps=frozenset(("rate",)), preview=True))


class TestCanPreview(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_administrator_and_system_manager(self):
        doc = frappe.new_doc("Carrier Tracking")
        self.assertTrue(fa.can_preview(doc))
        frappe.set_user("Guest")
        with patch.object(frappe, "get_roles", return_value=["System Manager"]):
            self.assertTrue(fa.can_preview(doc))

    def test_delete_or_set_user_permissions_right_only(self):
        doc = frappe.new_doc("Carrier Tracking")
        asked = []

        def has_permission(doctype, ptype, doc=None):
            asked.append(ptype)
            return ptype == "set_user_permissions"

        frappe.set_user("Guest")
        with patch.object(frappe, "get_roles", return_value=["Sales User"]), \
                patch.object(frappe, "has_permission", side_effect=has_permission):
            self.assertTrue(fa.can_preview(doc))
            self.assertEqual(asked, ["delete", "set_user_permissions"])
        with patch.object(frappe, "get_roles", return_value=["Sales User"]), \
                patch.object(frappe, "has_permission", return_value=False):
            self.assertFalse(fa.can_preview(doc))
            with self.assertRaises(frappe.PermissionError):
                fa.check_action(doc, "preview_request")


@patch.object(frappe, "log_error")
@patch.object(frappe.db, "commit")
@patch.object(frappe.db, "rollback")
@patch.object(frappe.db, "get_value", return_value=0)
class TestBookingFailure(FrappeTestCase):
    """A failure must not lose a booked AWB (#245). No carrier and no database."""
    def setUp(self):
        self.carrier = MagicMock()
        self.carrier.provider.name = "FedEx"
        self.carrier.provider.supports.return_value = False
        self.carrier.provider.book.return_value = BookingResult(awb="AWB1", package_ids=[])
        self.doc = MagicMock(docstatus=0, shipment_package_details=[], flags=frappe._dict())
        self.doc.name = "_Test CT"

    def book(self):
        with patch.object(shipping_actions, "prepare_booking", return_value=(self.carrier, MagicMock())):
            shipping_actions.book(self.doc)

    def test_a_failed_draft_save_gives_no_booking(self, *_):
        self.doc.save.side_effect = frappe.ValidationError("Courier Charges Too Low")
        with self.assertRaises(frappe.ValidationError):
            self.book()
        self.carrier.provider.book.assert_not_called()

    def test_the_draft_save_checks_permissions_and_the_submit_skips_the_courier_check(self, *_):
        flags = []
        self.doc.save.side_effect = lambda: flags.append(dict(self.doc.flags))
        self.doc.submit.side_effect = lambda: flags.append(dict(self.doc.flags))
        self.book()
        self.assertEqual(flags, [{}, {"ignore_permissions": True, "carrier_booked": True}])
        self.carrier.provider.cancel.assert_not_called()

    def test_a_failed_submit_cancels_the_awb_and_logs_it(self, _get, rollback, commit, log_error):
        self.doc.submit.side_effect = frappe.ValidationError("Late failure")
        with self.assertRaisesRegex(frappe.ValidationError, "Late failure.*AWB AWB1 is cancelled"):
            self.book()
        self.carrier.provider.cancel.assert_called_once_with("AWB1")
        rollback.assert_called_once()
        self.assertIn("AWB1", log_error.call_args.kwargs["title"])
        commit.assert_called_once()

    def test_a_failed_cancel_tells_the_user_to_cancel_on_the_portal(self, *_):
        self.doc.submit.side_effect = frappe.ValidationError("Late failure")
        self.carrier.provider.cancel.side_effect = ProviderError("no reply")
        with self.assertRaisesRegex(frappe.ValidationError, "AWB1 is NOT cancelled.*no reply.*portal"):
            self.book()


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
