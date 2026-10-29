import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.obsolete_items import obsolete_items as report
from rigpl_erpnext.tests.test_stock_reconciliation_check import insert_sle
from rigpl_erpnext.tests.test_variant_table import insert_item
from rigpl_erpnext.utils.stock_utils import get_warehouses

ITEM = "_Test RIGPL Obsolete Item"


class TestObsoleteItems(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_cancelled_sle_rows_are_not_counted(self):
        wh = get_warehouses()[0]
        insert_sle(ITEM, wh, 5, voucher_type="Stock Entry")
        insert_sle(ITEM, wh, 6, voucher_type="Stock Entry", is_cancelled=1)

        counts = report.get_counts([ITEM])

        self.assertEqual(counts["Stock Ledger Entry"], {ITEM: 1})

    def test_one_query_per_table(self):
        with assert_max_queries(len(report.COUNT_TABLES), test_case=self):
            report.get_counts([ITEM, "_Test RIGPL Other Item"])

    def test_attribute_and_quality_filters(self):
        insert_item(ITEM, attributes=[("Base Material", "_Test BM"), ("_Test BM Quality", "_Test Q")])
        filters = frappe._dict(eol="2026-01-01", is_pl_item=0, has_variants=1, bm="_Test BM")

        self.assertEqual([d.name for d in report.get_item_list(filters)], [ITEM])
        self.assertEqual(report.get_item_list(frappe._dict(filters, quality="_Test Q"))[0].name, ITEM)
        self.assertEqual(report.get_item_list(frappe._dict(filters, quality="_Test Other")), [])

    def test_quote_in_filter_does_not_change_the_query(self):
        filters = frappe._dict(eol="2026-01-01", bm="x' OR '1'='1", tt="x' OR '1'='1")
        self.assertEqual(report.get_items(filters), [])
