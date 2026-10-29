from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.stock_ledger_with_valuation import \
    stock_ledger_with_valuation as report
from rigpl_erpnext.tests.test_stock_reconciliation_check import insert_sle
from rigpl_erpnext.tests.test_variant_table import insert_item
from rigpl_erpnext.utils.stock_utils import get_warehouses

ITEM = "_Test RIGPL SLwV Item"


def run(**filters):
    return report.execute(frappe._dict(item=ITEM, from_date="2026-01-01", to_date="2026-01-31", **filters))[1]


class TestStockLedgerWithValuation(FrappeTestCase):
    def setUp(self):
        self.wh = get_warehouses()[0]
        insert_item(ITEM, variant_of="_Test RIGPL SLwV Template")

    def tearDown(self):
        frappe.db.rollback()

    def test_cancelled_rows_are_not_shown(self):
        insert_sle(ITEM, self.wh, 5, voucher_type="Stock Entry", voucher_no="_Test SE-1")
        insert_sle(ITEM, self.wh, 6, voucher_type="Stock Entry", voucher_no="_Test SE-2", is_cancelled=1)

        data = run()

        self.assertEqual([row[10] for row in data], ["_Test SE-1"])

    def test_query_count_does_not_grow_with_rows(self):
        for day in range(1, 11):
            insert_sle(ITEM, self.wh, day, voucher_type="Stock Entry", voucher_no="_Test SE-%s" % day)
        insert_sle(ITEM, self.wh, 11, voucher_type="Delivery Note", voucher_no="_Test DN-1")

        # The first run loads the DocType meta; then 1 SLE query + 1 per voucher type
        run()
        with assert_max_queries(3, test_case=self):
            data = run()
        self.assertEqual(len(data), 11)

    def test_quote_in_filter_does_not_change_the_query(self):
        self.assertEqual(run(warehouse="x' OR '1'='1"), [])


class TestStockLedgerLinks(FrappeTestCase):
    def links(self, voucher_type, doc):
        rows = [frappe._dict(voucher_type=voucher_type, voucher_no="V-1")]
        with patch.object(report.frappe, "get_all", return_value=[frappe._dict(name="V-1", **doc)]):
            return report.get_links(rows)[(voucher_type, "V-1")]

    def test_stock_entry_links_the_first_field_that_is_set(self):
        doc = dict(process_job_card=None, sales_order="", delivery_note_no="DN-1",
            sales_invoice_no="SI-1", purchase_order=None, purchase_receipt_no=None)
        self.assertEqual(self.links("Stock Entry", doc), ("Delivery Note", "DN-1"))

    def test_stock_entry_with_no_link(self):
        doc = {field: None for _, field in report.PARTY_LINKS["Stock Entry"]}
        self.assertEqual(self.links("Stock Entry", doc), (None, None))

    def test_invoice_links_the_customer(self):
        self.assertEqual(self.links("Sales Invoice", dict(customer="C-1")), ("Customer", "C-1"))
