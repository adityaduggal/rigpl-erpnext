"""Database tests of the tracking jobs. Raw rows (db_insert), rolled back after each test."""
from datetime import datetime, timedelta
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping import tracking
from rigpl_erpnext.rigpl_erpnext.shipping.base import Scan, TrackingResult
from rigpl_erpnext.rigpl_erpnext.shipping.settings import DEFAULTS, ShippingSettings

ACCOUNT, SHIPWAY_ACCOUNT = "_Test RIGPL DTDC", "_Test RIGPL Shipway"
TPT, TPT_SHIPWAY, TPT_NONE = "_Test RIGPL DTDC Air", "_Test RIGPL Speed Post", "_Test RIGPL By Hand"
SETTINGS = ShippingSettings(**DEFAULTS)


def insert(doctype, name, **fields):
    frappe.get_doc(dict(doctype=doctype, name=name, **fields)).db_insert()


def ctrack(name, carrier=TPT, days_old=10, status=st.IN_TRANSIT, docstatus=1, awb=None, **fields):
    created = now_datetime() - timedelta(days=days_old)
    values = dict(carrier_name=carrier, awb_number=awb or f"AWB{name}", status=status, docstatus=docstatus,
                  creation=created, modified=created, manual_exception_removed=0, posted_to_shipway=0, published=0)
    values.update(fields)
    insert("Carrier Tracking", name, **values)


def result(awb, status=st.DELIVERED, scans=1):
    return TrackingResult(awb=awb, status=status, status_code="DLV", delivery_date_time=datetime(2026, 10, 15, 17, 7),
                          destination="CHENNAI",
                          scans=[Scan(datetime(2026, 10, 14, 10, i), "HUB", f"S{i}") for i in range(scans)])


class TrackingCase(FrappeTestCase):
    def setUp(self):
        insert("Shipping Provider Account", ACCOUNT, account_name=ACCOUNT, provider="DTDC", enabled=1)
        insert("Shipping Provider Account", SHIPWAY_ACCOUNT, account_name=SHIPWAY_ACCOUNT, provider="Shipway", enabled=1)
        insert("Transporters", TPT, api_mode="Tracking Only", shipping_provider_account=ACCOUNT)
        insert("Transporters", TPT_SHIPWAY, api_mode="Tracking Only", shipping_provider_account=SHIPWAY_ACCOUNT,
               provider_service_code="12")
        insert("Transporters", TPT_NONE, api_mode="None")

    def tearDown(self):
        frappe.db.rollback()

    def selected(self):
        return {r["name"] for r in tracking.select_open_shipments(SETTINGS) if r["name"].startswith("_Test RIGPL")}


class TestSelection(TrackingCase):
    def test_poll_selects_like_the_old_job(self):
        ctrack("_Test RIGPL CT open")
        ctrack("_Test RIGPL CT draft", docstatus=0, status="")
        ctrack("_Test RIGPL CT new", days_old=0)
        ctrack("_Test RIGPL CT old", days_old=150)
        ctrack("_Test RIGPL CT done", status=st.DELIVERED)
        ctrack("_Test RIGPL CT rto", status=st.RTO)
        ctrack("_Test RIGPL CT manual", manual_exception_removed=1)
        ctrack("_Test RIGPL CT no awb", awb="NA")
        ctrack("_Test RIGPL CT fresh", last_update=now_datetime() - timedelta(hours=1))
        ctrack("_Test RIGPL CT no api", carrier=TPT_NONE)
        ctrack("_Test RIGPL CT sw pushed", carrier=TPT_SHIPWAY, posted_to_shipway=1)
        ctrack("_Test RIGPL CT sw not pushed", carrier=TPT_SHIPWAY)
        ctrack("_Test RIGPL CT sw old", carrier=TPT_SHIPWAY, posted_to_shipway=1, days_old=60)

        self.assertEqual(self.selected(), {"_Test RIGPL CT open", "_Test RIGPL CT draft", "_Test RIGPL CT sw pushed"})

    def test_selection_is_one_query(self):
        for i in range(5):
            ctrack(f"_Test RIGPL CT q{i}")
        with assert_max_queries(1, test_case=self):
            tracking.select_open_shipments(SETTINGS)


class TestApplyResults(TrackingCase):
    def rows(self, names):
        return [r for r in tracking.select_open_shipments(SETTINGS) if r["name"] in names]

    def test_batch_is_written_in_fixed_queries(self):
        names = [f"_Test RIGPL CT b{i}" for i in range(6)]
        for name in names:
            ctrack(name)
        rows = self.rows(names)
        results = {r["awb_number"]: result(r["awb_number"], scans=3) for r in rows}
        # 1 UPDATE, then scans: 1 read, 1 DELETE, 1 INSERT
        with assert_max_queries(4, test_case=self):
            counts = tracking.apply_tracking_results(rows, results, "Poll")

        self.assertEqual(counts, {st.DELIVERED: 6})
        doc = frappe.get_doc("Carrier Tracking", names[0])
        self.assertEqual((doc.status, doc.status_code, doc.tracking_source, doc.ship_to_city),
                         (st.DELIVERED, "DLV", "Poll", "CHENNAI"))
        self.assertEqual(len(doc.scans), 3)
        self.assertTrue(doc.last_update)

    def test_same_scans_are_not_written_again(self):
        ctrack("_Test RIGPL CT s1")
        rows = self.rows({"_Test RIGPL CT s1"})
        tracking.apply_tracking_results(rows, {rows[0]["awb_number"]: result(rows[0]["awb_number"], st.IN_TRANSIT, 2)}, "Poll")
        before = frappe.get_all("Courier Tracking Scans", filters={"parent": "_Test RIGPL CT s1"}, pluck="name")
        self.assertEqual(tracking.replace_changed_scans({"_Test RIGPL CT s1": result("x", scans=2).scans}), 0)
        after = frappe.get_all("Courier Tracking Scans", filters={"parent": "_Test RIGPL CT s1"}, pluck="name")
        self.assertEqual(sorted(before), sorted(after))

    def test_not_found_moves_only_last_update(self):
        ctrack("_Test RIGPL CT nf", status=st.IN_TRANSIT)
        rows = self.rows({"_Test RIGPL CT nf"})
        tracking.apply_tracking_results(rows, {rows[0]["awb_number"]: TrackingResult(rows[0]["awb_number"], "", found=False)}, "Poll")
        status, last_update = frappe.db.get_value("Carrier Tracking", "_Test RIGPL CT nf", ["status", "last_update"])
        self.assertEqual(status, st.IN_TRANSIT)
        self.assertTrue(last_update)

    def test_failed_batch_is_logged_and_others_continue(self):
        from rigpl_erpnext.rigpl_erpnext.shipping.base import ProviderError
        from rigpl_erpnext.rigpl_erpnext.shipping.providers.dtdc import DTDC

        ctrack("_Test RIGPL CT f1")
        # Error Log commits on insert in v13, so it is mocked
        with patch.object(DTDC, "track_many", side_effect=ProviderError("DTDC: down")), \
                patch("frappe.log_error") as log_error:
            counts = tracking.track_rows(self.rows({"_Test RIGPL CT f1"}), source="Poll")
        self.assertEqual(counts, {"failed": 1})
        log_error.assert_called_once()


class TestUnpublishAndClose(TrackingCase):
    def test_unpublish_is_one_update(self):
        now = now_datetime()
        ctrack("_Test RIGPL CT u old delivery", status=st.DELIVERED, published=1, route="u1",
               delivery_date_time=now - timedelta(days=8))
        ctrack("_Test RIGPL CT u new delivery", status=st.DELIVERED, published=1, route="u2",
               delivery_date_time=now - timedelta(days=2))
        ctrack("_Test RIGPL CT u cancelled", status=st.CANCELLED, published=1, route="u3")
        ctrack("_Test RIGPL CT u very old", status=st.IN_TRANSIT, published=1, route="u4", days_old=91)
        ctrack("_Test RIGPL CT u open", status=st.IN_TRANSIT, published=1, route="u5")
        with patch("frappe.website.render.clear_cache"), assert_max_queries(1, test_case=self):
            tracking.unpublish_ctracks(SETTINGS)

        published = set(frappe.get_all("Carrier Tracking", filters={"name": ["like", "_Test RIGPL CT u%"], "published": 1},
                                       pluck="name"))
        self.assertEqual(published, {"_Test RIGPL CT u new delivery", "_Test RIGPL CT u open"})

    def test_stale_trackings_are_polled_once_then_closed(self):
        ctrack("_Test RIGPL CT old a", days_old=200, published=1)
        ctrack("_Test RIGPL CT old b", days_old=200)
        ctrack("_Test RIGPL CT young", days_old=20)
        with patch.object(tracking, "track_rows", return_value={"Delivered": 1}) as track_rows, \
                patch.object(frappe.db, "commit"):
            frappe.db.set_value("Carrier Tracking", "_Test RIGPL CT old a", "status", st.DELIVERED)
            counts = tracking.refresh_and_close_stale(settings=SETTINGS)

        polled = {r["name"] for r in track_rows.call_args[0][0]}
        self.assertTrue({"_Test RIGPL CT old b"} <= polled)
        self.assertNotIn("_Test RIGPL CT young", polled)
        self.assertEqual(frappe.db.get_value("Carrier Tracking", "_Test RIGPL CT old b", "status"), st.CLOSED)
        self.assertEqual(frappe.db.get_value("Carrier Tracking", "_Test RIGPL CT old a", "status"), st.DELIVERED)
        self.assertGreaterEqual(counts["closed"], 1)
        comment = frappe.get_all("Comment", filters={"reference_doctype": "Carrier Tracking",
                                                     "reference_name": "_Test RIGPL CT old b"}, pluck="content")
        self.assertIn("Status before: In Transit", comment[0])

    def test_daily_job_does_not_close(self):
        with patch.object(tracking, "refresh_and_close_stale") as close, patch.object(tracking, "unpublish_ctracks"), \
                patch.object(frappe.db, "commit"):
            tracking.daily_shipping_jobs()
        close.assert_not_called()
