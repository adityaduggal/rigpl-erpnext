
import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.utils.stock_utils import get_wh_wise_qty, get_wh_wise_qty_for_items

WAREHOUSE = "_Test WWQ Stores"
ITEM_1 = "_Test WWQ Item 1"
ITEM_2 = "_Test WWQ Item 2"


def add_bin(item_code, actual_qty=0, reserved_qty=0):
    frappe.get_doc(
        doctype="Bin",
        name=frappe.generate_hash(length=10),
        item_code=item_code,
        warehouse=WAREHOUSE,
        actual_qty=actual_qty,
        reserved_qty=reserved_qty,
    ).db_insert()


class TestWhWiseQty(FrappeTestCase):
    def setUp(self):
        frappe.get_doc(
            doctype="Warehouse", name=WAREHOUSE, warehouse_name=WAREHOUSE, short_code="WWQ"
        ).db_insert()
        add_bin(ITEM_1, actual_qty=5, reserved_qty=2)
        add_bin(ITEM_2)

    def tearDown(self):
        frappe.db.rollback()

    def test_quantities_for_many_items(self):
        qty_dict = get_wh_wise_qty_for_items([ITEM_1, ITEM_2, "_Test WWQ No Bin"])

        self.assertEqual(sorted(qty_dict), [ITEM_1, ITEM_2])
        row = qty_dict[ITEM_1][0]
        self.assertEqual((row.actual, row.on_so, row.scode), (5, 2, "WWQ"))
        self.assertEqual(get_wh_wise_qty(ITEM_1), qty_dict[ITEM_1])

    def test_non_zero_leaves_out_empty_bins(self):
        qty_dict = get_wh_wise_qty_for_items([ITEM_1, ITEM_2], non_zero=True)

        self.assertEqual(sorted(qty_dict), [ITEM_1])
