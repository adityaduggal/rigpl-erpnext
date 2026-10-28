import datetime
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from rigpl_erpnext.rigpl_erpnext.report.stock_valuation import stock_valuation as report

WH = "Stores - T"
OTHER_WH = "Dead - T"


def sle(item, warehouse, qty, balance, day, value=0.0, rate=0.0, voucher_type="Stock Entry"):
    return frappe._dict(
        name=item,
        warehouse=warehouse,
        voucher_type=voucher_type,
        voucher_no="V-%s" % day,
        serial_no=None,
        actual_qty=qty,
        qty_after_transaction=balance,
        valuation_rate=rate,
        stock_value=value,
        posting_date=datetime.date(2026, 1, day),
    )


def make_report(date="2026-01-31", bin_qty=None, atts=None):
    sv = report.StockValuation(frappe._dict(date=date))
    sv.item_map = {
        "IT-1": frappe._dict(name="IT-1", description="Item 1", valuation_rate=50, is_purchase_item=1)
    }
    sv.att_map = {"IT-1": atts or {}}
    sv.bin_qty = bin_qty or {}
    sv.list_rates = {"IT-1": 120}
    sv.purchase_rates = {"IT-1": 80}
    return sv


def chunk_rows(sv, rows):
    """Run get_chunk_rows with the item values set in make_report, not read from the DB."""
    with patch.object(report.StockValuation, "load_item_values"):
        return sv.get_chunk_rows(rows)


class TestStockValuationRows(FrappeTestCase):
    def test_row_values_and_fifo_ages(self):
        sv = make_report(bin_qty={("IT-1", WH): 7})
        rows = [
            sle("IT-1", WH, 10, 10, 1, value=1000, rate=100),
            sle("IT-1", WH, -3, 7, 21, value=700, rate=100),
        ]
        data = chunk_rows(sv, rows)

        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row[:8], ["IT-1", "Item 1", WH, 7, 7, 120, 100, 700])
        self.assertEqual(row[18:21], [50, 80, 1])
        # 7 left from the 1 Jan slot: 30 days old on 31 Jan
        self.assertEqual(row[21:], [30, 30, 30])

    def test_last_sle_gives_value_and_rate(self):
        sv = make_report(date="2025-01-31")
        rows = [
            sle("IT-1", WH, 16, 16, 1, value=13120, rate=820),
            sle("IT-1", WH, -5, 11, 2, value=9020, rate=820),
        ]
        row = chunk_rows(sv, rows)[0]

        self.assertEqual(row[3], 11)
        self.assertEqual(row[7], 9020)

    def test_pairs_sold_out_are_not_shown(self):
        sv = make_report()
        rows = [
            sle("IT-1", WH, 5, 5, 1),
            sle("IT-1", OTHER_WH, 4, 4, 1),
            sle("IT-1", OTHER_WH, -4, 0, 2),
        ]
        data = chunk_rows(sv, rows)

        self.assertEqual([row[2] for row in data], [WH])

    def test_qty_of_half_or_less_is_not_shown(self):
        sv = make_report(date="2025-01-31")
        self.assertEqual(chunk_rows(sv, [sle("IT-1", WH, 0.5, 0.5, 1)]), [])

    def test_attribute_cells(self):
        sv = make_report(atts={"Base Material": "Carbide", "Carbide Quality": "K10", "d1_mm": "6.0000"})
        row = sv.get_row(("IT-1", WH), 1, [[1, datetime.date(2026, 1, 1)]], sle("IT-1", WH, 1, 1, 1))

        self.assertEqual(row[8:11], ["Carbide", "K10", "-"])
        self.assertEqual(row[11:16], [6.0, None, None, None, None])
        self.assertEqual(row[16:18], ["-", "-"])

    def test_hss_quality_comes_before_carbide_quality(self):
        sv = make_report(atts={"HSS Quality": "H-1X", "Carbide Quality": "K10"})
        row = sv.get_row(("IT-1", WH), 1, [[1, datetime.date(2026, 1, 1)]], sle("IT-1", WH, 1, 1, 1))
        self.assertEqual(row[9], "H-1X")


class TestStockValuationPairs(FrappeTestCase):
    def test_today_reads_only_bins_in_stock(self):
        sv = make_report(date=nowdate(), bin_qty={("IT-1", WH): 3, ("IT-1", OTHER_WH): 0})
        self.assertEqual(sv.get_stocked_pairs(), {("IT-1", WH)})

    def test_past_date_reads_all_pairs(self):
        sv = make_report(date=add_days(nowdate(), -1), bin_qty={("IT-1", WH): 3})
        self.assertIsNone(sv.get_stocked_pairs())


class TestStockValuationFilters(FrappeTestCase):
    def test_quote_in_filter_does_not_change_the_query(self):
        with self.assertRaises(frappe.ValidationError):
            report.get_items(frappe._dict(bm="Carbide' OR '1'='1"))
