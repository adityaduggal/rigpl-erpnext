"""Dashboard and stale clean-up button of Shipping Provider Account (#169)."""
from datetime import datetime, timedelta
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.shipping import dashboard
from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.settings import DEFAULTS, ShippingSettings
from rigpl_erpnext.rigpl_erpnext.shipping.tracking import select_stale

ACCOUNT, OTHER = "_Test RIGPL Dash DTDC", "_Test RIGPL Dash Other"
TPT, TPT_OTHER = "_Test RIGPL Dash Air", "_Test RIGPL Dash Other Air"


def insert(doctype, name, **fields):
    frappe.get_doc(dict(doctype=doctype, name=name, **fields)).db_insert()


def ctrack(name, carrier=TPT, created=None, status=st.IN_TRANSIT, **fields):
    created = created or now_datetime()
    insert("Carrier Tracking", name, carrier_name=carrier, awb_number=f"AWB{name}", status=status, docstatus=1,
           creation=created, modified=created, manual_exception_removed=0, **fields)


class TestDashboard(FrappeTestCase):
    def setUp(self):
        for account, tpt in ((ACCOUNT, TPT), (OTHER, TPT_OTHER)):
            insert("Shipping Provider Account", account, account_name=account, provider="DTDC", enabled=1)
            insert("Transporters", tpt, api_mode="Tracking Only", shipping_provider_account=account)

    def tearDown(self):
        frappe.db.rollback()

    def test_counts_by_status_for_the_account_and_period(self):
        day = datetime(2026, 10, 10, 12, 0)
        ctrack("_Test RIGPL D1", created=day, status=st.DELIVERED, pickup_date="2026-10-10",
               delivery_date_time="2026-10-13 10:00:00")
        ctrack("_Test RIGPL D2", created=day, status=st.DELIVERED, pickup_date="2026-10-10",
               delivery_date_time="2026-10-12 10:00:00")
        ctrack("_Test RIGPL D3", created=day, status=st.IN_TRANSIT)
        ctrack("_Test RIGPL D4", created=day, status="")
        ctrack("_Test RIGPL D5", created=datetime(2026, 9, 1), status=st.DELIVERED)  # before the period
        ctrack("_Test RIGPL D6", carrier=TPT_OTHER, created=day, status=st.DELIVERED)  # other account
        ctrack("_Test RIGPL D7", created=datetime(2026, 10, 20, 23, 59), status=st.RTO)  # last day counts

        dashboard.get_account_summary(ACCOUNT, "2026-10-01", "2026-10-20")  # fills the settings cache
        with assert_max_queries(2, test_case=self):
            data = dashboard.get_account_summary(ACCOUNT, "2026-10-01", "2026-10-20")

        self.assertEqual(data["total"], 5)
        self.assertEqual(data["by_status"], [
            {"status": st.IN_TRANSIT, "count": 1}, {"status": st.DELIVERED, "count": 2},
            {"status": st.RTO, "count": 1}, {"status": dashboard.NO_STATUS, "count": 1},
        ])
        self.assertEqual(data["avg_transit_days"], 2.5)
        self.assertEqual(data["stale_open"], 0)

    def test_stale_count_and_selection_are_per_account(self):
        old = now_datetime() - timedelta(days=200)
        ctrack("_Test RIGPL S1", created=old)
        ctrack("_Test RIGPL S2", carrier=TPT_OTHER, created=old)
        settings = ShippingSettings(**DEFAULTS)
        self.assertEqual({r["name"] for r in select_stale(settings, account=ACCOUNT)}, {"_Test RIGPL S1"})
        today = str(now_datetime().date())
        self.assertEqual(dashboard.get_account_summary(ACCOUNT, today, today)["stale_open"], 1)

    def test_wrong_period(self):
        with self.assertRaises(frappe.ValidationError):
            dashboard.get_account_summary(ACCOUNT, "2026-10-20", "2026-10-01")

    def test_close_runs_once_at_a_time(self):
        with patch("frappe.utils.background_jobs.get_jobs", return_value={}), patch("frappe.enqueue") as enqueue:
            dashboard.close_stale_trackings(ACCOUNT)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs["account"], ACCOUNT)
        self.assertEqual(enqueue.call_args.kwargs["job_name"], dashboard.close_job_name(ACCOUNT))

        running = {frappe.local.site: [dashboard.close_job_name(ACCOUNT)]}
        with patch("frappe.utils.background_jobs.get_jobs", return_value=running), patch("frappe.enqueue") as enqueue:
            with self.assertRaises(frappe.ValidationError):
                dashboard.close_stale_trackings(ACCOUNT)
        enqueue.assert_not_called()
