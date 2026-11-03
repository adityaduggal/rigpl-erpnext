"""
Buying reports after the move from '%s' SQL to frappe.qb (#187). Each filter value has a quote:
the old reports put it into the SQL text and failed.
"""
import frappe

from rigpl_erpnext.rigpl_erpnext.report.items_on_indent import items_on_indent
from rigpl_erpnext.rigpl_erpnext.report.pending_purchase_orders import pending_purchase_orders
from rigpl_erpnext.rigpl_erpnext.report.raw_material_needed import raw_material_needed
from rigpl_erpnext.rigpl_erpnext.report.sub_contracting_mismatch import sub_contracting_mismatch
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw
from rigpl_erpnext.tests.test_stock_reports import BM, insert_bin, insert_stock_item
from rigpl_erpnext.utils.other_utils import auto_round_up
from rigpl_erpnext.utils.stock_utils import get_quantities_for_items

ITEM = "_Test RIGPL O'Brien Buying Item"
ITEM_2 = "_Test RIGPL O'Brien Buying Item 2"
SERVICE = "_Test RIGPL O'Brien Coating"
SUPPLIER = "_Test RIGPL O'Brien Supplier"
OTHER_SUPPLIER = "_Test RIGPL O'Brien Supplier 2"
QUALITY = "_Test RIGPL O'Grade"
BRAND = "_Test RIGPL O'Brand"
DATE = "2026-01-15"


def insert_purchase_item(name, d1, extra=()):
    insert_stock_item(name, d1, extra=extra)
    frappe.db.set_value("Item", name, {"is_purchase_item": 1}, update_modified=False)


def insert_reorder(item_code, level, idx=1):
    raw("Item Reorder", parent=item_code, parenttype="Item", parentfield="reorder_levels", idx=idx,
        warehouse_reorder_level=level)


def insert_indent(item_code, qty, ordered=0, date=DATE, status="Pending"):
    mr = raw("Material Request", transaction_date=date, docstatus=1, status=status, material_request_type="Purchase")
    raw("Material Request Item", parent=mr, parenttype="Material Request", parentfield="items", idx=1,
        item_code=item_code, qty=qty, ordered_qty=ordered, schedule_date=date, description=item_code, uom="Nos")
    return mr


def insert_po(item_code, qty, received=0, subcontracted_item=None, supplier=SUPPLIER, date=DATE,
        status="To Receive and Bill", **values):
    po = raw("Purchase Order", supplier=supplier, transaction_date=date, docstatus=1, status=status,
        is_subcontracting=1 if subcontracted_item else 0)
    values.setdefault("conversion_factor", 1)
    raw("Purchase Order Item", parent=po, parenttype="Purchase Order", parentfield="items", idx=1,
        item_code=item_code, subcontracted_item=subcontracted_item, qty=qty, received_qty=received,
        schedule_date=date, description=item_code, stock_uom="Nos", **values)
    return po


def insert_subcontracting_warehouse(name):
    raw("Warehouse", name=name, warehouse_name=name, short_code=name[-6:], listing_serial=99,
        warehouse_type="Subcontracting", is_group=0, disabled=0, is_subcontracting_warehouse=1)


class TestItemsOnIndent(ReportTestCase):
    def test_pending_indents_with_attribute_columns(self):
        insert_purchase_item(ITEM, "6", extra=[(f"{BM} Quality", QUALITY), ("w1_mm", "2")])
        insert_purchase_item(ITEM_2, "3")
        mine = insert_indent(ITEM, 5, ordered=2)
        other = insert_indent(ITEM_2, 4)
        insert_indent(ITEM, 5, ordered=5)
        insert_indent(ITEM, 5, date="2026-02-10")
        insert_indent(ITEM, 5, status="Stopped")
        filters = frappe._dict(date="2026-01-31", bm=BM)

        data = self.assert_queries(2, lambda: items_on_indent.execute(filters)[1])

        # No quality sorts first
        self.assertEqual([row[0] for row in data], [other, mine])
        self.assertEqual(data[1][3:], [ITEM, ITEM, 5, "Nos", 2, BM, QUALITY, "_Test RIGPL O'Drill", 6, 2])
        self.assertEqual(data[0][7:], [None, BM, "-", "_Test RIGPL O'Drill", 3, None])
        self.assertEqual([row[0] for row in items_on_indent.execute(frappe._dict(filters, qa=QUALITY))[1]], [mine])
        self.assertRaises(frappe.ValidationError, items_on_indent.execute, frappe._dict(date=DATE))


class TestPendingPurchaseOrders(ReportTestCase):
    def test_subcontract_rows(self):
        insert_purchase_item(ITEM, "6")
        po = insert_po(SERVICE, 10, received=4, subcontracted_item=ITEM, conversion_factor=2,
            reference_dn="_Test RIGPL O'JC", returned_qty=1)
        insert_po(SERVICE, 10, subcontracted_item=ITEM, supplier=OTHER_SUPPLIER)
        insert_po(SERVICE, 10, subcontracted_item=ITEM, status="Closed")
        insert_po(SERVICE, 10, received=10, subcontracted_item=ITEM)
        insert_po(ITEM, 10)

        data = self.assert_queries(1, lambda: pending_purchase_orders.execute(frappe._dict(subcontracting=1,
            date=DATE, bm=BM, supplier=SUPPLIER, item=SERVICE))[1])

        self.assertEqual([(row[0], row[4], row[6], row[7], row[8], row[11], row[12]) for row in data],
            [(po, ITEM, 6, 10, 1, 2, "_Test RIGPL O'JC")])

    def test_urgency_uses_calculated_rol(self):
        insert_purchase_item(ITEM, "6")
        insert_reorder(ITEM, 10)
        po = insert_po(ITEM, 10)
        insert_po(ITEM, 10, date="2026-02-10")
        qty = get_quantities_for_items([frappe.get_doc("Item", ITEM)])[ITEM]
        self.assertGreater(qty.calculated_rol, 0)

        data = self.assert_queries(4, lambda: pending_purchase_orders.execute(frappe._dict(subcontracting=0,
            date="2026-01-31", bm=BM, supplier=SUPPLIER))[1])

        # The old report read calculated_rol from the PO row, so Min Qty was always empty here
        self.assertEqual([row[0] for row in data], [po])
        self.assertEqual(data[0][11:], ["Needed in Next 15~30 Days", auto_round_up(qty.calculated_rol)])
