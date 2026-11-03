"""Carrier Tracking web page access (#83): signed links, expiry and the linked user. No database writes."""
from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.rigpl_erpnext.shipping import access
from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.settings import DEFAULTS, ShippingSettings

SETTINGS = ShippingSettings(**DEFAULTS)  # 90 days published, 7 days after delivery
NOW = datetime(2026, 11, 3, 12, 0)
MODULE = "rigpl_erpnext.rigpl_erpnext.shipping.access"


def ctrack(name="CTRACK-T1", **kw):
    values = dict(doctype="Carrier Tracking", name=name, route="abc123", published=1, creation=datetime(2026, 10, 1),
                  status=st.IN_TRANSIT, delivery_date_time=None, receiver_document="Customer",
                  receiver_name="_Test Customer")
    values.update(kw)
    return frappe._dict(values)


def link_args(doc, exp=None):
    exp = int((exp or access.access_expires_on(doc, SETTINGS)).timestamp())
    return {"exp": str(exp), "sig": access.sign(doc.name, exp)}


class TestAccess(FrappeTestCase):
    def setUp(self):
        patcher = patch(f"{MODULE}.get_shipping_settings", return_value=SETTINGS)
        patcher.start()
        self.addCleanup(patcher.stop)

    def guest_can_view(self, doc, args):
        return access.can_view(doc, args, user="Guest", now=NOW)

    def test_expiry_is_creation_plus_published_days_or_7_days_after_delivery(self):
        self.assertEqual(access.access_expires_on(ctrack(), SETTINGS), datetime(2026, 12, 30))
        delivered = ctrack(status=st.DELIVERED, delivery_date_time=datetime(2026, 10, 30, 9, 0))
        self.assertEqual(access.access_expires_on(delivered, SETTINGS), datetime(2026, 11, 6, 9, 0))

    def test_guest_with_a_valid_link_can_view(self):
        doc = ctrack()
        self.assertTrue(self.guest_can_view(doc, link_args(doc)))

    def test_guest_is_denied_without_or_with_a_bad_link(self):
        doc = ctrack()
        good = link_args(doc)
        for args in ({}, {"exp": good["exp"]}, {"exp": good["exp"], "sig": "0" * 64},
                     {"exp": ["!=", ""], "sig": good["sig"]}, {"exp": "12a", "sig": good["sig"]}):
            self.assertFalse(self.guest_can_view(doc, args), args)
        self.assertFalse(self.guest_can_view(doc, None))

    def test_the_link_of_another_ctrack_is_denied(self):
        self.assertFalse(self.guest_can_view(ctrack(), link_args(ctrack(name="CTRACK-T2"))))

    def test_an_expired_link_is_denied(self):
        doc = ctrack()
        self.assertFalse(self.guest_can_view(doc, link_args(doc, exp=datetime(2026, 11, 1))))

    def test_a_link_stops_when_the_shipment_is_delivered_7_days_ago(self):
        doc = ctrack()
        args = link_args(doc)  # signed before delivery: good until 30 Dec
        doc.update({"status": st.DELIVERED, "delivery_date_time": datetime(2026, 10, 20)})
        self.assertFalse(self.guest_can_view(doc, args))

    def test_linked_contact_user_can_view_and_other_users_cannot(self):
        doc = ctrack()
        with patch(f"{MODULE}.is_receiver_contact", return_value=True), \
                patch("frappe.has_permission", return_value=False):
            self.assertTrue(access.can_view(doc, {}, user="buyer@example.com", now=NOW))
        with patch(f"{MODULE}.is_receiver_contact", return_value=False), \
                patch("frappe.has_permission", return_value=False):
            self.assertFalse(access.can_view(doc, {}, user="other@example.com", now=NOW))

    def test_nobody_can_view_after_the_expiry(self):
        doc = ctrack(status=st.DELIVERED, delivery_date_time=datetime(2026, 10, 1))
        with patch(f"{MODULE}.is_receiver_contact", return_value=True), patch("frappe.has_permission", return_value=True):
            self.assertFalse(access.can_view(doc, link_args(doc), user="Administrator", now=NOW))

    def test_route_is_a_token_never_the_name(self):
        self.assertTrue(access.needs_new_route("CTRACK00001", "ctrack00001"))
        self.assertTrue(access.needs_new_route("CTRACK00001", ""))
        self.assertFalse(access.needs_new_route("CTRACK00001", "f3a9c0d1e2b4a5968778"))
        route = access.new_route()
        self.assertEqual(len(route), access.ROUTE_LENGTH)
        self.assertNotEqual(route, access.new_route())


class TestTrackingPage(FrappeTestCase):
    def page(self, args):
        doc = frappe.get_doc({"doctype": "Carrier Tracking", "awb_number": "AWB-SECRET", "status": st.IN_TRANSIT,
                              "receiver_document": "Customer", "receiver_name": "_Test Customer", "published": 1,
                              "route": "abc123"})
        doc.name, doc.creation = "CTRACK-T1", datetime.now()
        context = frappe._dict(doc.as_dict(), doc=doc, docname=doc.name, page_title=doc.name)
        # frappe.session is a LocalProxy: patch.object cannot restore it, so set_user is used
        user = frappe.session.user
        frappe.set_user("Guest")
        try:
            with patch(f"{MODULE}.request_args", return_value=args), \
                    patch(f"{MODULE}.get_shipping_settings", return_value=SETTINGS):
                doc.get_context(context)
        finally:
            frappe.set_user(user)
        return doc, context

    def test_a_denied_view_keeps_nothing_of_the_shipment(self):
        _, context = self.page({})
        self.assertTrue(context.expired)
        self.assertNotIn("awb_number", context)
        self.assertNotIn("docname", context)
        self.assertEqual(context.page_title, "Shipment Tracking")
        self.assertIsNone(context.doc.awb_number)
        self.assertEqual((context.no_cache, context.metatags["robots"]), (1, "noindex,nofollow"))

    def test_a_signed_link_shows_the_page(self):
        doc = ctrack(creation=datetime.now())
        _, context = self.page(link_args(doc))
        self.assertFalse(context.get("expired"))
        self.assertEqual(context.awb_number, "AWB-SECRET")
