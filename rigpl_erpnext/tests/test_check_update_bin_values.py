import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.scheduled_tasks.check_update_bin_values import check_bins, get_bin_change

WH_1 = "_Test RIGPL BinChk WH 1"
WH_2 = "_Test RIGPL BinChk WH 2"
ITEM = "_Test RIGPL BinChk Item"
# Reads for check_bins with no changes: 7 for the quantities, 1 for the Bins of the items and
# 1 for the Bins with a wrong projected qty.
READ_QUERIES = 9


def insert_stock_item(name):
    frappe.get_doc(
        doctype="Item", name=name, item_code=name, item_name=name, item_group="All Item Groups",
        stock_uom="Nos", is_stock_item=1, has_variants=0, disabled=0, made_to_order=0,
    ).db_insert()


def insert_warehouse(name):
    frappe.get_doc(doctype="Warehouse", name=name, warehouse_name=name, short_code=name[-4:]).db_insert()


def insert_bin(item_code, warehouse, **qty):
    doc = frappe.get_doc(
        doctype="Bin", name=frappe.generate_hash(length=10), item_code=item_code,
        warehouse=warehouse, stock_uom="Nos", **qty
    )
    doc.set_projected_qty()
    doc.db_insert()
    return doc.name


def insert_doc(doctype, child_doctype, parentfield, parent_values, rows):
    name = frappe.generate_hash(length=10)
    frappe.get_doc(doctype=doctype, name=name, docstatus=1, **parent_values).db_insert()
    for idx, row in enumerate(rows, start=1):
        frappe.get_doc(
            doctype=child_doctype, name=frappe.generate_hash(length=10), parent=name,
            parenttype=doctype, parentfield=parentfield, idx=idx, docstatus=1, **row
        ).db_insert()


def insert_sales_order(item_code, warehouse, qty, delivered_qty=0):
    insert_doc("Sales Order", "Sales Order Item", "items", {"status": "To Deliver and Bill"}, [{
        "item_code": item_code, "warehouse": warehouse, "qty": qty, "stock_qty": qty,
        "delivered_qty": delivered_qty, "conversion_factor": 1,
    }])


def insert_purchase_order(item_code, warehouse, qty, conversion_factor=1):
    insert_doc("Purchase Order", "Purchase Order Item", "items", {"status": "To Receive and Bill"}, [{
        "item_code": item_code, "warehouse": warehouse, "qty": qty, "received_qty": 0,
        "conversion_factor": conversion_factor, "delivered_by_supplier": 0,
    }])


def insert_material_request(item_code, warehouse, qty, mr_type="Purchase"):
    insert_doc("Material Request", "Material Request Item", "items",
        {"status": "Pending", "material_request_type": mr_type}, [{
            "item_code": item_code, "warehouse": warehouse, "qty": qty, "stock_qty": qty,
            "ordered_qty": 0,
        }])


def insert_process_sheet(production_item, fg_warehouse, quantity, rm_item=None, rm_warehouse=None,
        rm_qty=0):
    rows = []
    if rm_item:
        rows.append({"item_code": rm_item, "source_warehouse": rm_warehouse, "calculated_qty": rm_qty,
            "qty": 0})
    insert_doc("Process Sheet", "Process Sheet Items", "rm_consumed", {
        "production_item": production_item, "fg_warehouse": fg_warehouse, "quantity": quantity,
        "produced_qty": 0, "status": "Submitted",
    }, rows)


def get_bin_qty(name):
    return frappe.db.get_value("Bin", name, ["reserved_qty", "ordered_qty", "indented_qty",
        "planned_qty", "reserved_qty_for_production", "projected_qty"], as_dict=1)


class TestGetBinChange(FrappeTestCase):
    def setUp(self):
        self.row = frappe._dict(actual_qty=10, reserved_qty=1, ordered_qty=2, indented_qty=3,
            planned_qty=4, reserved_qty_for_production=5, reserved_qty_for_sub_contract=0,
            projected_qty=13)

    def test_fixes_all_wrong_fields_in_one_change(self):
        expected = dict(reserved_qty=6, ordered_qty=7, indented_qty=8, planned_qty=9,
            reserved_qty_for_production=10)

        change = get_bin_change(self.row, expected, 3)

        self.assertEqual(change, dict(expected, projected_qty=10 + 7 + 8 + 9 - 6 - 10))

    def test_no_change_when_equal(self):
        expected = dict(reserved_qty=1, ordered_qty=2, indented_qty=3, planned_qty=4,
            reserved_qty_for_production=5.0001)

        self.assertEqual(get_bin_change(self.row, expected, 3), {})

    def test_missing_expected_qty_is_zero(self):
        self.assertEqual(get_bin_change(self.row, {}, 3), dict(reserved_qty=0, ordered_qty=0,
            indented_qty=0, planned_qty=0, reserved_qty_for_production=0, projected_qty=10))

    def test_fixes_only_projected_qty(self):
        self.row.projected_qty = 99
        expected = {field: self.row[field] for field in ("reserved_qty", "ordered_qty",
            "indented_qty", "planned_qty", "reserved_qty_for_production")}

        self.assertEqual(get_bin_change(self.row, expected, 3), {"projected_qty": 13})


class TestCheckBins(FrappeTestCase):
    def setUp(self):
        insert_warehouse(WH_1)
        insert_warehouse(WH_2)
        insert_stock_item(ITEM)

    def tearDown(self):
        frappe.db.rollback()

    def test_each_warehouse_gets_its_own_qty(self):
        bin_1 = insert_bin(ITEM, WH_1, actual_qty=20, reserved_qty=99)
        bin_2 = insert_bin(ITEM, WH_2, ordered_qty=5)
        insert_sales_order(ITEM, WH_1, qty=10, delivered_qty=4)
        insert_sales_order(ITEM, WH_2, qty=3)
        insert_purchase_order(ITEM, WH_1, qty=2, conversion_factor=5)
        insert_material_request(ITEM, WH_2, qty=7)
        insert_material_request(ITEM, WH_2, qty=2, mr_type="Material Issue")
        insert_process_sheet(ITEM, WH_1, quantity=8, rm_item=ITEM, rm_warehouse=WH_2, rm_qty=6)

        check_bins([ITEM])

        self.assertEqual(get_bin_qty(bin_1), dict(reserved_qty=6, ordered_qty=10, indented_qty=0,
            planned_qty=8, reserved_qty_for_production=0, projected_qty=20 + 10 + 8 - 6))
        self.assertEqual(get_bin_qty(bin_2), dict(reserved_qty=3, ordered_qty=0, indented_qty=5,
            planned_qty=0, reserved_qty_for_production=6, projected_qty=5 - 3 - 6))

    def test_creates_missing_bin(self):
        insert_sales_order(ITEM, WH_1, qty=4)

        check_bins([ITEM])

        name = frappe.db.get_value("Bin", {"item_code": ITEM, "warehouse": WH_1})
        self.assertEqual(get_bin_qty(name).reserved_qty, 4)

    def test_fixes_wrong_projected_qty(self):
        name = insert_bin(ITEM, WH_1, actual_qty=5)
        frappe.db.set_value("Bin", name, "projected_qty", 1, update_modified=False)

        check_bins([ITEM])

        self.assertEqual(get_bin_qty(name).projected_qty, 5)

    def test_reads_do_not_grow_with_items(self):
        for count in (2, 5):
            items = [f"{ITEM} {count} {idx}" for idx in range(count)]
            for item in items:
                insert_stock_item(item)
                insert_bin(item, WH_1, actual_qty=1, reserved_qty=2)
                insert_sales_order(item, WH_1, qty=2)

            with assert_max_queries(READ_QUERIES, test_case=self):
                check_bins(items)

    def test_one_write_per_wrong_bin(self):
        items = [f"{ITEM} W {idx}" for idx in range(3)]
        for idx, item in enumerate(items):
            insert_stock_item(item)
            insert_bin(item, WH_1, reserved_qty=50 + idx, ordered_qty=1)

        with assert_max_queries(READ_QUERIES + len(items), test_case=self):
            check_bins(items)
