import datetime
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.validations import delivery_note, stock_entry
from rigpl_erpnext.utils.stock_utils import get_reconciliations_after, get_warehouses

ITEM = "_Test RIGPL SR Item"


def insert_sle(item, warehouse, day, time="10:00:00", voucher_type="Stock Reconciliation",
        is_cancelled=0, qty=1, voucher_no=None):
    """Insert a raw Stock Ledger Entry row on `day` of January 2026."""
    doc = frappe.get_doc(
        doctype="Stock Ledger Entry",
        name=frappe.generate_hash(length=10),
        item_code=item,
        warehouse=warehouse,
        posting_date=datetime.date(2026, 1, day),
        posting_time=time,
        voucher_type=voucher_type,
        voucher_no=voucher_no or "_Test V-%s" % day,
        actual_qty=qty,
        qty_after_transaction=qty,
        is_cancelled=is_cancelled,
    )
    doc.db_insert()
    return doc


class TestReconciliationsAfter(FrappeTestCase):
    def setUp(self):
        self.wh = get_warehouses()[0]

    def tearDown(self):
        frappe.db.rollback()

    def test_cancelled_and_earlier_rows_do_not_count(self):
        insert_sle(ITEM, self.wh, 5)
        insert_sle(ITEM, self.wh, 20, is_cancelled=1)
        insert_sle(ITEM, self.wh, 20, voucher_type="Stock Entry")

        self.assertEqual(get_reconciliations_after([(ITEM, self.wh)], "2026-01-10", "10:00:00"), {})

    def test_same_time_counts_only_when_inclusive(self):
        insert_sle(ITEM, self.wh, 10, "10:00:00")

        self.assertIn((ITEM, self.wh), get_reconciliations_after([(ITEM, self.wh)], "2026-01-10", "10:00:00"))
        self.assertEqual(
            get_reconciliations_after([(ITEM, self.wh)], "2026-01-10", "10:00:00", inclusive=False), {})

    def test_first_reconciliation_per_pair(self):
        insert_sle(ITEM, self.wh, 25, voucher_no="_Test SR-2")
        insert_sle(ITEM, self.wh, 10, "11:00:00", voucher_no="_Test SR-1")

        with assert_max_queries(1, test_case=self):
            srs = get_reconciliations_after([(ITEM, self.wh), (ITEM, None)], "2026-01-10", "10:00:00")

        self.assertEqual(list(srs), [(ITEM, self.wh)])
        self.assertEqual(srs[(ITEM, self.wh)].voucher_no, "_Test SR-1")


def sr_row(day):
    return frappe._dict(voucher_no="_Test SR", posting_date=datetime.date(2026, 1, day),
        posting_time=datetime.timedelta(hours=10))


class TestValidationMessages(FrappeTestCase):
    def dn(self):
        return frappe._dict(name="_Test DN", posting_date="2026-01-10", posting_time="10:00:00",
            items=[frappe._dict(idx=1, item_code=ITEM, warehouse="WH", against_sales_order="SO")])

    def check_dn(self, srs):
        with patch.object(delivery_note, "check_draft_dn"), \
                patch.object(delivery_note, "get_linked_so_data"), \
                patch.object(delivery_note, "check_strict_po_rules"), \
                patch.object(delivery_note, "copy_address_and_check"), \
                patch.object(delivery_note, "check_price_list"), \
                patch.object(delivery_note, "get_reconciliations_after", return_value=srs):
            delivery_note.validate(self.dn(), "validate")

    def test_dn_reconciliation_on_a_later_date(self):
        with self.assertRaisesRegex(frappe.ValidationError, "after the posting date"):
            self.check_dn({(ITEM, "WH"): sr_row(11)})

    def test_dn_reconciliation_on_the_same_date(self):
        with self.assertRaisesRegex(frappe.ValidationError, "after the posting time"):
            self.check_dn({(ITEM, "WH"): sr_row(10)})

    def test_dn_without_reconciliation_passes(self):
        self.check_dn({})

    def test_stock_entry_lists_source_and_target_warehouse(self):
        # Not a frappe._dict: its .items is the dict method
        ste = SimpleNamespace(company=None, posting_date="2026-01-10", posting_time="10:00:00",
            items=[frappe._dict(idx=1, item_code=ITEM, s_warehouse="WH-S", t_warehouse="WH-T")])
        srs = {(ITEM, "WH-S"): sr_row(11), (ITEM, "WH-T"): sr_row(12)}
        frappe.local.message_log = []
        with patch.object(stock_entry, "get_reconciliations_after", return_value=srs):
            with self.assertRaisesRegex(frappe.ValidationError, "Cannot Proceed"):
                stock_entry.check_stock_recon(ste)

        messages = [frappe.parse_json(m).message for m in frappe.local.message_log][:-1]
        self.assertEqual(len(messages), 2)
        self.assertIn("for WH-S there is Stock Reconciliation _Test SR at 2026-01-11", messages[0])
        self.assertIn("for WH-T", messages[1])
