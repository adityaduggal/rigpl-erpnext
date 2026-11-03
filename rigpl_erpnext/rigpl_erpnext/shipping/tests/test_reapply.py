"""Re-apply Status Map from the stored scans (#169). Raw rows, rolled back after each test."""
from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.shipping import dashboard, tracking
from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.seed_rules import SEED_RULES
from rigpl_erpnext.rigpl_erpnext.shipping.status_map import StatusResolver, seed_rules

ACCOUNT, OTHER = "_Test RIGPL Re DTDC", "_Test RIGPL Re Other"
TPT, TPT_OTHER = "_Test RIGPL Re Air", "_Test RIGPL Re Other Air"


def insert(doctype, name, **fields):
    frappe.get_doc(dict(doctype=doctype, name=name, **fields)).db_insert()


def ctrack(name, scans, carrier=TPT, status=st.IN_TRANSIT, **fields):
    insert("Carrier Tracking", name, carrier_name=carrier, awb_number=f"AWB{name}", status=status, docstatus=1,
           manual_exception_removed=0, **fields)
    for idx, (time, detail) in enumerate(scans, start=1):
        insert("Courier Tracking Scans", frappe.generate_hash(length=10), parent=name, parenttype="Carrier Tracking",
               parentfield="scans", idx=idx, docstatus=1, time=time, location="HUB", status_detail=detail)


def resolver():
    return StatusResolver("DTDC", rules=seed_rules("DTDC", SEED_RULES["DTDC"]))


T1, T2, T3 = datetime(2024, 6, 23, 9, 0), datetime(2024, 6, 24, 10, 0), datetime(2024, 6, 24, 11, 51)


class TestReapply(FrappeTestCase):
    def setUp(self):
        for account, tpt in ((ACCOUNT, TPT), (OTHER, TPT_OTHER)):
            insert("Shipping Provider Account", account, account_name=account, provider="DTDC", enabled=1)
            insert("Transporters", tpt, api_mode="Tracking Only", shipping_provider_account=account)

    def tearDown(self):
        frappe.db.rollback()

    def plan(self):
        return tracking.plan_status_changes(tracking.stored_scans(ACCOUNT), resolver())

    def test_delivered_scan_wins_even_when_out_of_order(self):
        ctrack("_Test RIGPL R1", [(T1, "IBMN: In Transit-1"), (T3, "DLV: OTP Based Delivered-5 A Person"),
                                  (T2, "OUTDLV: Out For Delivery-2")])
        old, values = self.plan()["_Test RIGPL R1"]
        self.assertEqual(old, st.IN_TRANSIT)
        self.assertEqual(values, {"status": st.DELIVERED, "status_code": "DLV", "delivery_date_time": T3})

    def test_latest_mapped_scan_when_not_delivered(self):
        ctrack("_Test RIGPL R2", [(T1, "IBMN: In Transit-1"), (T2, "OUTDLV: Out For Delivery-2"),
                                  (T3, "ZZNEW: Something new")])
        self.assertEqual(self.plan()["_Test RIGPL R2"][1]["status"], st.OUT_FOR_DELIVERY)

    def test_final_statuses_are_not_changed_and_closed_only_becomes_final(self):
        ctrack("_Test RIGPL R3", [(T1, "IBMN: In Transit-1")], status=st.DELIVERED)
        ctrack("_Test RIGPL R4", [(T1, "DLV: Delivered-1")], status=st.CANCELLED)
        ctrack("_Test RIGPL R5", [(T1, "IBMN: In Transit-1")], status=st.CLOSED)
        ctrack("_Test RIGPL R6", [(T1, "SETRTO: Set RTO initiated")], status=st.CLOSED)
        plan = self.plan()
        self.assertNotIn("_Test RIGPL R3", plan)
        self.assertNotIn("_Test RIGPL R4", plan)
        self.assertNotIn("_Test RIGPL R5", plan)
        self.assertEqual(plan["_Test RIGPL R6"][1]["status"], st.RTO)

    def test_other_accounts_and_unmapped_scans_are_left(self):
        ctrack("_Test RIGPL R7", [(T1, "DLV: Delivered-1")], carrier=TPT_OTHER)
        ctrack("_Test RIGPL R8", [(T1, "ZZNEW: Something new")])
        self.assertEqual(self.plan(), {})

    def test_job_writes_in_fixed_queries_and_leaves_comments(self):
        names = [f"_Test RIGPL W{i}" for i in range(6)]
        for name in names:
            ctrack(name, [(T1, "IBMN: In Transit-1"), (T3, "DLV: Delivered-1")])
        with patch("rigpl_erpnext.rigpl_erpnext.shipping.tracking.record_unknown"), \
                patch("rigpl_erpnext.rigpl_erpnext.shipping.status_map.load_rules",
                      return_value={"DTDC": seed_rules("DTDC", SEED_RULES["DTDC"])}), \
                patch.object(frappe.db, "commit"), patch("frappe.publish_realtime"):
            # account provider, scans, 1 UPDATE, 1 INSERT of tracking comments, 1 INSERT of the account comment
            with assert_max_queries(8, test_case=self):
                counts = tracking.reapply_status_map(ACCOUNT)
        self.assertEqual(counts, {"In Transit -> Delivered": 6})
        self.assertEqual(frappe.db.get_value("Carrier Tracking", names[0], ["status", "status_code"]), (st.DELIVERED, "DLV"))
        comments = frappe.get_all("Comment", filters={"reference_name": names[0]}, pluck="content")
        self.assertIn("In Transit -> Delivered (DLV)", comments[0])

    def test_dry_run_writes_nothing(self):
        ctrack("_Test RIGPL D1", [(T3, "DLV: Delivered-1")])
        with patch("rigpl_erpnext.rigpl_erpnext.shipping.status_map.load_rules",
                   return_value={"DTDC": seed_rules("DTDC", SEED_RULES["DTDC"])}):
            self.assertEqual(tracking.reapply_status_map(ACCOUNT, dry_run=True), {"In Transit -> Delivered": 1})
        self.assertEqual(frappe.db.get_value("Carrier Tracking", "_Test RIGPL D1", "status"), st.IN_TRANSIT)

    def test_button_enqueues_once(self):
        with patch("frappe.utils.background_jobs.get_jobs", return_value={}), patch("frappe.enqueue") as enqueue:
            dashboard.reapply_status_map(ACCOUNT)
        self.assertEqual(enqueue.call_args.args[0], dashboard.REAPPLY_JOB)
        running = {frappe.local.site: [f"reapply_status:{ACCOUNT}"]}
        with patch("frappe.utils.background_jobs.get_jobs", return_value=running), patch("frappe.enqueue"):
            with self.assertRaises(frappe.ValidationError):
                dashboard.reapply_status_map(ACCOUNT)
