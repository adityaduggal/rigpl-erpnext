import datetime
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.stock_ageing_rigpl import stock_ageing_rigpl as report
from rigpl_erpnext.utils.stock_utils import get_sle_for_items, get_warehouses

WH = "Stores - T"
OTHER_WH = "Dead - T"
ITEM = "_Test RIGPL Ageing Item"


def sle(item, warehouse, qty, balance, day, voucher_no=None, voucher_type="Stock Entry"):
    return frappe._dict(
        name=item,
        warehouse=warehouse,
        voucher_type=voucher_type,
        voucher_no=voucher_no or "V-%s" % day,
        serial_no=None,
        actual_qty=qty,
        qty_after_transaction=balance,
        posting_date=datetime.date(2026, 1, day),
    )


def make_report(to_date="2026-01-31", warehouse_wise=1):
    sa = report.StockAgeing(frappe._dict(to_date=to_date, show_ageing_warehouse_wise=warehouse_wise))
    sa.item_map = {"IT-1": frappe._dict(name="IT-1", description="Item 1", stock_uom="Nos")}
    return sa


def chunk_rows(sa, rows, atts=None):
    """Run get_chunk_rows with the attributes given here, not read from the DB."""
    with patch.object(report, "get_attribute_map", return_value={"IT-1": atts or {}}):
        return sa.get_chunk_rows(rows)


class TestStockAgeingRows(FrappeTestCase):
    def test_fifo_ages(self):
        rows = [
            sle("IT-1", WH, 10, 10, 1),
            sle("IT-1", WH, 5, 15, 21),
            sle("IT-1", WH, -12, 3, 25),
        ]
        row = chunk_rows(make_report(), rows)[0]

        # 10 from 1 Jan and 2 from 21 Jan are used, 3 from 21 Jan are left: 10 days old
        self.assertEqual(row[:4], ["IT-1", "Item 1", WH, 3])
        self.assertEqual(row[4:7], [10, 10, 10])

    def test_same_voucher_transfer_keeps_the_old_date(self):
        rows = [
            sle("IT-1", WH, 10, 10, 1),
            sle("IT-1", WH, -1, 9, 21, voucher_no="SE-1"),
            sle("IT-1", WH, 1, 10, 21, voucher_no="SE-1"),
        ]
        row = chunk_rows(make_report(), rows)[0]

        # The old report dated the returned piece 21 Jan (latest age 10)
        self.assertEqual(row[5:7], [30, 30])

    def test_item_wise_adds_up_the_warehouses(self):
        rows = [
            sle("IT-1", WH, 4, 4, 1),
            sle("IT-1", OTHER_WH, 6, 6, 21),
        ]
        data = chunk_rows(make_report(warehouse_wise=0), rows)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0][:3], ["IT-1", "Item 1", 10])
        self.assertEqual(data[0][4:6], [30, 10])

    def test_sold_out_pairs_are_not_shown(self):
        rows = [
            sle("IT-1", WH, 5, 5, 1),
            sle("IT-1", OTHER_WH, 4, 4, 1),
            sle("IT-1", OTHER_WH, -4, 0, 2),
        ]
        data = chunk_rows(make_report(), rows)

        self.assertEqual([row[2] for row in data], [WH])

    def test_attribute_cells(self):
        atts = {"Base Material": "Carbide", "Carbide Quality": "K10", "d1_mm": "6.0000"}
        row = chunk_rows(make_report(), [sle("IT-1", WH, 1, 1, 1)], atts)[0]

        self.assertEqual(row[7:14], ["Nos", "-", "Carbide", "-", "-", "K10", "-"])
        self.assertEqual(row[14:], [6.0, None, None, None, None, None])

    def test_hss_quality_comes_before_carbide_quality(self):
        atts = {"HSS Quality": "H-1X", "Carbide Quality": "K10"}
        row = chunk_rows(make_report(), [sle("IT-1", WH, 1, 1, 1)], atts)[0]
        self.assertEqual(row[12], "H-1X")


class TestStockAgeingPairs(FrappeTestCase):
    def test_today_reads_only_bins_in_stock(self):
        sa = make_report(to_date=nowdate())
        bin_qty = {("IT-1", WH): 3, ("IT-1", OTHER_WH): 0}
        with patch.object(report, "get_bin_qty", return_value=bin_qty):
            self.assertEqual(sa.get_stocked_pairs([WH, OTHER_WH]), [("IT-1", WH)])

    def test_past_date_reads_all_pairs(self):
        sa = make_report(to_date=add_days(nowdate(), -1))
        self.assertIsNone(sa.get_stocked_pairs([WH]))


class TestStockAgeingQueries(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_quote_in_filter_does_not_change_the_query(self):
        with self.assertRaises(frappe.ValidationError):
            report.get_items(frappe._dict(bm="Carbide' OR '1'='1"))

    def test_cancelled_sle_rows_are_not_read(self):
        warehouse = get_warehouses()[0]
        for idx, cancelled in enumerate((0, 1)):
            frappe.get_doc(
                doctype="Stock Ledger Entry",
                name="_Test RIGPL Ageing SLE %s" % idx,
                item_code=ITEM,
                warehouse=warehouse,
                posting_date="2026-01-01",
                posting_time="10:00:00",
                actual_qty=5,
                qty_after_transaction=5,
                is_cancelled=cancelled,
            ).db_insert()

        with assert_max_queries(1, test_case=self):
            rows = get_sle_for_items([ITEM], [warehouse], datetime.date(2026, 1, 31))

        self.assertEqual(len(rows), 1)

    def test_group_warehouse_gives_the_warehouses_under_it(self):
        group = frappe.db.get_value("Warehouse", {"is_group": 1, "disabled": 0})
        expected = frappe.get_all(
            "Warehouse",
            filters={
                "name": ("in", frappe.db.get_descendants("Warehouse", group) or [""]),
                "is_group": 0,
                "disabled": 0,
            },
            pluck="name",
        )
        self.assertEqual(sorted(get_warehouses(group)), sorted(expected))

    def test_unknown_warehouse_gives_no_warehouses(self):
        self.assertEqual(get_warehouses("_Test RIGPL No Such Warehouse"), [])
