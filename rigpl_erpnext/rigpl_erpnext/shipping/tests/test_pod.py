"""Proof of delivery jobs (#171). Raw rows, providers and file writes mocked, rolled back."""
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.shipping import pod, tracking
from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.base import Label, ProviderError
from rigpl_erpnext.rigpl_erpnext.shipping.providers.fedex import FedEx
from rigpl_erpnext.rigpl_erpnext.shipping.status_map import load_rules

from .test_tracking import SETTINGS, TPT as TPT_DTDC, TrackingCase, ctrack, insert, result

FEDEX_ACCOUNT, TPT_FEDEX = "_Test RIGPL FedEx", "_Test RIGPL FedEx Priority"


def fake_file(filename, content, doctype, name, is_private=0):
    return frappe._dict(file_url=f"/private/files/{filename}")


class PodCase(TrackingCase):
    def setUp(self):
        super().setUp()
        insert("Shipping Provider Account", FEDEX_ACCOUNT, account_name=FEDEX_ACCOUNT, provider="FedEx", enabled=1)
        insert("Transporters", TPT_FEDEX, api_mode="Booking and Tracking", shipping_provider_account=FEDEX_ACCOUNT)
        load_rules()  # keep the status map read out of the query counts
        pod.get_carriers([TPT_FEDEX])  # and the first table-column lookups of get_all


class TestNeedsPod(FrappeTestCase):
    def test_only_new_delivered_fedex_without_pod(self):
        row = {"status": st.IN_TRANSIT, "pod_file": None, "provider": "FedEx"}
        self.assertTrue(pod.needs_pod(row, st.DELIVERED))
        self.assertFalse(pod.needs_pod(row, st.IN_TRANSIT))
        self.assertFalse(pod.needs_pod(dict(row, status=st.DELIVERED), st.DELIVERED))
        self.assertFalse(pod.needs_pod(dict(row, pod_file="/private/files/x.pdf"), st.DELIVERED))
        self.assertFalse(pod.needs_pod(dict(row, provider="DTDC"), st.DELIVERED))


class TestPodTrigger(PodCase):
    def test_one_job_for_the_new_delivered_fedex_trackings(self):
        ctrack("_Test RIGPL P1", carrier=TPT_FEDEX)
        ctrack("_Test RIGPL P2", carrier=TPT_FEDEX)
        ctrack("_Test RIGPL P3", carrier=TPT_FEDEX, pod_file="/private/files/old.pdf")
        ctrack("_Test RIGPL P4")  # DTDC has no POD API
        names = {"_Test RIGPL P1", "_Test RIGPL P2", "_Test RIGPL P3", "_Test RIGPL P4"}
        rows = [r for r in tracking.select_open_shipments(SETTINGS) if r["name"] in names]
        results = {r["awb_number"]: result(r["awb_number"]) for r in rows}
        with patch("frappe.enqueue") as enqueue:
            tracking.apply_tracking_results(rows, results, "Poll")
        enqueue.assert_called_once()
        self.assertEqual(sorted(enqueue.call_args.kwargs["names"]), ["_Test RIGPL P1", "_Test RIGPL P2"])
        self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])

    def test_no_job_when_nothing_is_delivered(self):
        ctrack("_Test RIGPL P5", carrier=TPT_FEDEX)
        rows = [r for r in tracking.select_open_shipments(SETTINGS) if r["name"] == "_Test RIGPL P5"]
        with patch("frappe.enqueue") as enqueue:
            tracking.apply_tracking_results(rows, {rows[0]["awb_number"]: result(rows[0]["awb_number"], st.IN_TRANSIT)},
                                            "Poll")
        enqueue.assert_not_called()


@patch.object(frappe.db, "commit")
@patch.object(pod, "save_file", side_effect=fake_file)
class TestFetchPods(PodCase):
    def delivered(self, name, carrier=TPT_FEDEX, days=1, **fields):
        ctrack(name, carrier=carrier, status=st.DELIVERED, delivery_date_time=now_datetime() - timedelta(days=days),
               **fields)

    def test_pods_are_saved_with_one_update_and_errors_logged_once(self, _save, _commit):
        for i in range(4):
            self.delivered(f"_Test RIGPL F{i}")

        def get_pod(provider, awb):
            if awb == "AWB_Test RIGPL F3":
                raise ProviderError("FedEx has no proof of delivery yet")
            return Label(f"POD-{awb}.pdf", b"%PDF")

        names = [f"_Test RIGPL F{i}" for i in range(4)]
        with patch.object(FedEx, "get_pod", autospec=True, side_effect=get_pod), \
                patch("frappe.log_error") as log_error:
            # 1 select, 3 for the carriers, 1 UPDATE (the File inserts are mocked)
            with assert_max_queries(5, test_case=self):
                counts = pod.fetch_pods(names)
        self.assertEqual(counts, {"fetched": 3, "failed": 1})
        log_error.assert_called_once()
        self.assertIn("_Test RIGPL F3", log_error.call_args.args[0])
        self.assertEqual(frappe.db.get_value("Carrier Tracking", "_Test RIGPL F0", "pod_file"),
                         "/private/files/POD-AWB_Test RIGPL F0.pdf")
        self.assertFalse(frappe.db.get_value("Carrier Tracking", "_Test RIGPL F3", "pod_file"))

    def test_daily_retry_selects_recent_delivered_fedex_without_pod(self, _save, _commit):
        self.delivered("_Test RIGPL R1")
        self.delivered("_Test RIGPL R2", days=pod.POD_RETRY_DAYS + 5)  # too old
        self.delivered("_Test RIGPL R3", pod_file="/private/files/have.pdf")
        self.delivered("_Test RIGPL R4", carrier=TPT_DTDC)
        ctrack("_Test RIGPL R5", carrier=TPT_FEDEX, status=st.IN_TRANSIT)
        with patch.object(pod, "fetch_rows", return_value={}) as fetch_rows:
            pod.retry_missing_pods()
        selected = {r["name"] for r in fetch_rows.call_args.args[0] if r["name"].startswith("_Test RIGPL")}
        self.assertEqual(selected, {"_Test RIGPL R1"})

    def test_daily_job_retries_pods(self, _save, _commit):
        with patch.object(tracking, "unpublish_ctracks"), patch.object(tracking, "retry_missing_pods") as retry:
            tracking.daily_shipping_jobs()
        retry.assert_called_once()
