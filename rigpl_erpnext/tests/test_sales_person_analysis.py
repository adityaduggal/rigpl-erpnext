from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.sales_person_analysis import sales_person_analysis as report

FILTERS = dict(doc_type="Sales Order", based_on="Master", from_date="2026-01-01", to_date="2026-03-31")


class TestSalesPersonAnalysis(FrappeTestCase):
    def test_three_queries_for_all_sales_persons(self):
        with assert_max_queries(3, test_case=self):
            report.execute(frappe._dict(FILTERS))

    def test_quote_in_filter_does_not_change_the_query(self):
        data = report.execute(frappe._dict(FILTERS, sales_person="x' OR '1'='1"))[1]
        self.assertEqual(data, [])

    def test_totals_go_to_their_sales_person(self):
        totals = {"Sales Order": {"SP-1": (100,)}, "Sales Invoice": {"SP-1": (80, 30), "SP-2": (5, 0)}}
        persons = [("SP-1", "Person 1", 1000), ("SP-2", "Person 2", None), ("SP-3", "Person 3", 0)]
        with patch.object(report, "get_totals", side_effect=lambda f, doctype, *a: totals[doctype]), \
                patch.object(report, "get_persons", return_value=persons):
            data = report.get_entries(frappe._dict(FILTERS))

        self.assertEqual(data, [
            ["Person 1", 1000, 100, 80, 30],
            ["Person 2", None, None, 5, None],
            ["Person 3", None, None, None, None],
        ])
