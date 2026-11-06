#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
Orders To Dispatch has ref_doctype Packing Slip, as in v12. Dispatch RIGPL has the report right on
Packing Slip but not on Sales Order, so a Dispatch user can open it and make the Delivery Note.
"""
import frappe
from frappe.desk.query_report import run

from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw

USER = "_test_rigpl_dispatch@example.com"
REPORT = "Orders To Dispatch"


class TestDispatchReport(ReportTestCase):
    def setUp(self):
        # db_insert, no hooks: see tests/test_report_permissions.py
        raw("User", name=USER, email=USER, first_name="_Test RIGPL Dispatch", user_type="System User",
            enabled=1)
        raw("Has Role", parent=USER, parenttype="User", parentfield="roles", role="Dispatch RIGPL")
        frappe.clear_cache(user=USER)

    def test_ref_doctype(self):
        self.assertEqual(frappe.db.get_value("Report", REPORT, "ref_doctype"), "Packing Slip")

    def test_dispatch_user_opens_report(self):
        frappe.set_user(USER)
        result = run(REPORT, filters={})
        self.assertTrue(result["columns"])
