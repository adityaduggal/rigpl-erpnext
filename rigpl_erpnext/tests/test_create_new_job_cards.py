from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.manufacturing_rigpl.utils.batch_qty_utils import get_open_so_items
from rigpl_erpnext.rigpl_erpnext.scheduled_tasks import create_new_job_cards as cnj

OPEN_SO = "_Test RIGPL CNJ SO Open"
CLOSED_SO = "_Test RIGPL CNJ SO Closed"


def d(**kwargs):
    return frappe._dict(kwargs)


def insert_so(name, status):
    frappe.get_doc({"doctype": "Sales Order", "name": name, "docstatus": 1, "status": status}).db_insert()


def insert_so_item(name, parent, qty, delivered_qty):
    frappe.get_doc({
        "doctype": "Sales Order Item", "name": name, "parent": parent, "parenttype": "Sales Order",
        "parentfield": "items", "qty": qty, "delivered_qty": delivered_qty, "docstatus": 1,
    }).db_insert()


class TestGetOpenSoItems(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_returns_only_pending_rows_of_open_sales_orders(self):
        insert_so(OPEN_SO, "To Deliver and Bill")
        insert_so(CLOSED_SO, "Closed")
        insert_so_item("_Test CNJ Pending", OPEN_SO, 10, 4)
        insert_so_item("_Test CNJ Delivered", OPEN_SO, 10, 10)
        insert_so_item("_Test CNJ Closed", CLOSED_SO, 10, 0)

        with assert_max_queries(1, test_case=self):
            result = get_open_so_items(["_Test CNJ Pending", "_Test CNJ Delivered", "_Test CNJ Closed"])
        self.assertEqual(result, {"_Test CNJ Pending"})

    def test_no_queries_for_no_items(self):
        with assert_max_queries(0, test_case=self):
            self.assertEqual(get_open_so_items([]), set())


class TestCleanupJobCards(FrappeTestCase):
    def test_execute_routes_each_job_card(self):
        job_cards = [
            d(name="JC-CLOSED", sales_order_item="SOI-CLOSED", total_qty=5, for_quantity=5),
            d(name="JC-OPEN", sales_order_item="SOI-OPEN", total_qty=0, for_quantity=0),
            d(name="JC-ZERO", sales_order_item=None, total_qty=0, for_quantity=5),
            d(name="JC-999", sales_order_item=None, total_qty=5, for_quantity=5),
        ]
        with patch.object(cnj.frappe, "get_all", return_value=job_cards), \
                patch.object(cnj, "get_open_so_items", return_value={"SOI-OPEN"}) as open_so, \
                patch.object(cnj, "short_close", return_value=1) as short_close, \
                patch.object(cnj, "save_or_delete", return_value=(1, 0)) as save_or_delete:
            cnj.execute()

        open_so.assert_called_once_with(["SOI-CLOSED", "SOI-OPEN"])
        short_close.assert_called_once_with("JC-CLOSED")
        save_or_delete.assert_called_once_with("JC-ZERO")

    def check_save_or_delete(self, total_qty):
        jcd = MagicMock(total_qty=total_qty, for_quantity=5, process_sheet="PS-1")
        with patch.object(cnj.frappe, "get_doc", return_value=jcd), \
                patch.object(cnj.frappe, "delete_doc") as delete_doc:
            result = cnj.save_or_delete("JC-1")
        jcd.save.assert_called_once()
        return result, delete_doc

    def test_save_or_delete_deletes_when_qty_still_zero(self):
        result, delete_doc = self.check_save_or_delete(0)
        self.assertEqual(result, (1, 1))
        delete_doc.assert_called_once_with(cnj.JC_DOCTYPE, "JC-1", for_reload=True)

    def test_save_or_delete_keeps_job_card_with_qty(self):
        result, delete_doc = self.check_save_or_delete(3)
        self.assertEqual(result, (1, 0))
        delete_doc.assert_not_called()
