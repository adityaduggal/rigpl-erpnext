"""Courier Tracking RIGPL report (#173)."""
from datetime import datetime

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.courier_tracking_rigpl import courier_tracking_rigpl as report
from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.validations import cost_over_limit

from .test_dashboard import insert

TPT, TPT_OTHER = "_Test RIGPL Report Air", "_Test RIGPL Report Ground"
PERIOD = {"from_date": "2026-09-01", "to_date": "2026-10-20"}


def ctrack(name, created, status, carrier=TPT, docstatus=1, manual_exception_removed=0, **fields):
    insert("Carrier Tracking", name, carrier_name=carrier, awb_number=f"AWB{name}", status=status,
           docstatus=docstatus, creation=created, modified=created,
           manual_exception_removed=manual_exception_removed, **fields)


def run(report_type, **filters):
    columns, data, _, chart, summary = report.execute(dict(PERIOD, report_type=report_type, transporter=TPT,
                                                           **filters))
    fields = [c["fieldname"] for c in columns]
    return [dict(zip(fields, row)) for row in data], chart, summary


def card(summary, label):
    return next(c["value"] for c in summary if c["label"] == label)


class TestReportHelpers(FrappeTestCase):
    def test_percentile_nearest_rank(self):
        self.assertEqual(report.percentile(list(range(1, 11)), 90), 9)
        self.assertEqual(report.percentile([5], 90), 5)
        self.assertEqual(report.percentile([], 90), 0)

    def test_cost_over_limit_keeps_validation_rule(self):
        self.assertTrue(cost_over_limit(30, 1000, 2))
        self.assertFalse(cost_over_limit(20, 1000, 2))
        self.assertFalse(cost_over_limit(30, 0, 2))
        self.assertFalse(cost_over_limit(30, 1000, None))
        self.assertTrue(cost_over_limit(30, 1000, 0))  # the save validation treats 0 as a limit

    def test_report_treats_max_percent_zero_as_no_limit(self):
        row = frappe._dict(shipment_cost=30, courier_charged=10, amount=1000, max_percent=0)
        report.annotate_cost(row)
        self.assertEqual((row.over_limit, row.difference, row.cost_percent), (0, -20, 3))
        row.max_percent = 2
        report.annotate_cost(row)
        self.assertEqual(row.over_limit, 1)

    def test_aggregate_performance(self):
        def t(created, status, pickup=None, delivered=None, expected=None, carrier=TPT):
            return {"carrier_name": carrier, "creation": created, "status": status, "pickup_date": pickup,
                    "delivery_date_time": delivered, "expected_delivery_date": expected}

        rows = report.aggregate_performance([
            t("2026-09-02", st.DELIVERED, "2026-09-02", "2026-09-04 10:00:00", "2026-09-05"),
            t("2026-09-03", st.DELIVERED, "2026-09-03", "2026-09-09 10:00:00", "2026-09-06"),
            t("2026-09-04", st.RTO),
            t("2026-09-05", st.CANCELLED),
            t("2026-09-06", st.CLOSED),
            t("2026-10-01", st.IN_TRANSIT),
        ])
        self.assertEqual([r.month for r in rows], ["2026-09", "2026-10"])
        sep = rows[0]
        self.assertEqual((sep.shipped, sep.delivered, sep.rto, sep.closed), (4, 2, 1, 1))
        self.assertEqual((sep.avg_days, sep.p90_days, sep.max_days, sep.on_time), (4, 6, 6, 50))
        self.assertEqual((rows[1].shipped, rows[1].delivered, rows[1].on_time), (1, 0, 0))


class TestCourierTrackingReport(FrappeTestCase):
    def setUp(self):
        insert("Transporters", TPT, max_percent_of_invoice_value=2)
        insert("Transporters", TPT_OTHER)
        sep, octo = datetime(2026, 9, 10, 10), datetime(2026, 10, 5, 10)
        ctrack("_Test RIGPL R1", created=sep, status=st.DELIVERED, pickup_date="2026-09-10",
               delivery_date_time="2026-09-13 10:00:00", expected_delivery_date="2026-09-14",
               pod_file="/files/pod.pdf", shipment_cost=30, courier_charged=0, amount=1000)
        ctrack("_Test RIGPL R2", created=octo, status=st.DELIVERED, pickup_date="2026-10-05",
               delivery_date_time="2026-10-06 10:00:00", shipment_cost=10, amount=1000)
        ctrack("_Test RIGPL R3", created=octo, status=st.IN_TRANSIT)
        ctrack("_Test RIGPL R4", created=datetime(2026, 10, 20, 23, 59), status=st.RTO)  # last day counts
        ctrack("_Test RIGPL R5", created=datetime(2025, 1, 5), status=st.IN_TRANSIT)  # before the period
        ctrack("_Test RIGPL R6", created=octo, status=st.IN_TRANSIT, docstatus=2)  # cancelled document
        ctrack("_Test RIGPL R7", created=octo, status=st.EXCEPTION, manual_exception_removed=1)
        ctrack("_Test RIGPL R8", carrier=TPT_OTHER, created=octo, status=st.IN_TRANSIT)

    def tearDown(self):
        frappe.db.rollback()

    def test_each_view_runs_one_query_with_chart_and_cards(self):
        for report_type in report.REPORT_TYPES:
            with self.subTest(report_type=report_type):
                with assert_max_queries(1, test_case=self):
                    rows, chart, summary = run(report_type)
                self.assertTrue(rows)
                self.assertTrue(chart["data"]["labels"])
                self.assertTrue(summary)

    def test_pending_ignores_dates_and_honours_transporter(self):
        rows, chart, summary = run(report.PENDING)
        # R5 is before the period; R6 is cancelled, R7 has its exception removed, R8 is another transporter
        self.assertEqual({r["name"] for r in rows}, {"_Test RIGPL R3", "_Test RIGPL R4", "_Test RIGPL R5"})
        self.assertEqual(card(summary, "Pending"), len(rows))

    def test_old_exceptions_skip_cancelled_and_old_rows_and_keep_last_day(self):
        rows, _, _ = run(report.OLD_EXCEPTIONS)
        self.assertEqual({r["name"] for r in rows}, {"_Test RIGPL R3", "_Test RIGPL R4", "_Test RIGPL R7"})

    def test_detailed_and_status_filter(self):
        rows, _, summary = run(report.DETAILED)
        self.assertEqual(len(rows), 5)  # R1-R4 and R7
        self.assertEqual(card(summary, "Delivered"), 2)
        rows, _, _ = run(report.DETAILED, status=st.RTO)
        self.assertEqual([r["name"] for r in rows], ["_Test RIGPL R4"])

    def test_grouped_views(self):
        rows, _, _ = run(report.TOTAL_AWB)
        self.assertEqual((rows[0]["total"], rows[0]["delivered"], rows[0]["exceptions"]), (5, 2, 1))
        rows, _, summary = run(report.AVG_DELIVERY)
        self.assertEqual((rows[0]["delivered"], rows[0]["max_days"], rows[0]["min_days"]), (2, 3, 1))
        self.assertEqual(card(summary, "Overall Avg Days"), 2)
        rows, chart, summary = run(report.POD_COVERAGE)
        self.assertEqual((rows[0]["with_pod"], rows[0]["without_pod"], rows[0]["coverage"]), (1, 1, 50))
        self.assertEqual(chart["barOptions"], {"stacked": 1})

    def test_cost_vs_charged(self):
        rows, _, summary = run(report.COST)
        by_name = {r["name"]: r for r in rows}
        self.assertEqual(set(by_name), {"_Test RIGPL R1", "_Test RIGPL R2"})
        self.assertEqual(by_name["_Test RIGPL R1"]["over_limit"], 1)
        self.assertIsNone(by_name["_Test RIGPL R2"]["over_limit"])  # 0 shows as an empty cell
        self.assertEqual(card(summary, "Over Limit"), 1)

    def test_carrier_performance_by_month(self):
        rows, chart, _ = run(report.PERFORMANCE)
        self.assertEqual([r["month"] for r in rows], ["2026-09", "2026-10"])
        self.assertEqual(chart["type"], "line")
        self.assertEqual(chart["data"]["datasets"][0]["values"], [100, 0])  # Oct has no expected date

    def test_filter_value_is_a_parameter(self):
        rows, _, _ = run(report.DETAILED, awb_no="x' OR '1'='1")
        self.assertEqual(rows, [])

    def test_unknown_report_type_and_wrong_period_throw(self):
        with self.assertRaises(frappe.ValidationError):
            report.execute({"report_type": "Everything"})
        with self.assertRaises(frappe.ValidationError):
            report.execute({"report_type": report.DETAILED, "from_date": "2026-10-02", "to_date": "2026-10-01"})
