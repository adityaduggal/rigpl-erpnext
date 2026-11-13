"""
Item, Warehouse, Purchase Receipt and Made to Order validations after the move from '%s' SQL to
parameters (#187). Each name or value has a quote: the old code put it into the SQL text and failed.
"""
from unittest.mock import Mock, patch

import frappe
from erpnext.stock.stock_ledger import NegativeStockError
from rohit_common.utils.rohit_common_utils import fn_check_digit

from rigpl_erpnext.rigpl_erpnext.validations import delivery_note
from rigpl_erpnext.rigpl_erpnext.validations import warehouse as warehouse_validation
from rigpl_erpnext.rigpl_erpnext.validations.item import generate_item_code
from rigpl_erpnext.rigpl_erpnext.validations.purchase_receipt import get_existing_ste
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw
from rigpl_erpnext.utils.item_utils import get_desc
from rigpl_erpnext.utils.stock_utils import get_stock_shortfalls

TEXT_ATT = "_Test RIGPL O'Code Attribute"
NUM_ATT = "_Test RIGPL O'Num Attribute"
TOOL_TYPE = "_Test RIGPL O'Tool Type"
MTO = "Made to Order Item Attributes"


def insert_attribute(name, numeric=0, use_in_item_code=1):
    raw("Item Attribute", name=name, attribute_name=name, numeric_values=numeric, use_in_item_code=use_in_item_code)


def insert_value(attribute, value, abbr, serial=None, description=None):
    return raw("Item Attribute Value", parent=attribute, parenttype="Item Attribute",
        parentfield="item_attribute_values", attribute_value=value, abbr=abbr, serial=serial,
        description=description)


def variant(*attributes):
    rows = [frappe._dict(attribute=a, attribute_value=v, idx=i) for a, v, i in attributes]
    return frappe._dict(variant_of="_Test RIGPL O'Template", attributes=rows)


class TestItemCode(ReportTestCase):
    def test_abbr_by_idx_serial_and_check_digit(self):
        insert_attribute(TEXT_ATT)
        insert_attribute(NUM_ATT, numeric=1)
        insert_value(TEXT_ATT, "O'Value", "AB")
        tt_row = insert_value("Tool Type", TOOL_TYPE, "TT", serial="0ABC")
        doc = variant(("Tool Type", TOOL_TYPE, 2), (NUM_ATT, "6", 3), (TEXT_ATT, "O'Value", 1))

        serial, code = self.assert_queries(2, lambda: generate_item_code(doc, "autoname"))

        self.assertEqual(serial, [["0ABC", tt_row]])
        self.assertEqual(code, "ABTT0ABC" + str(fn_check_digit("ABTT0ABC")))

    def test_missing_tool_type_or_value_throws(self):
        insert_attribute(TEXT_ATT)
        insert_value(TEXT_ATT, "O'Value", "AB")

        self.assertRaisesRegex(frappe.ValidationError, "Tool Type is needed", generate_item_code,
            variant((TEXT_ATT, "O'Value", 1)), "autoname")
        self.assertRaisesRegex(frappe.ValidationError, "No Item Attribute Value", generate_item_code,
            variant((TEXT_ATT, "O'Missing", 1)), "autoname")

    def test_get_desc(self):
        insert_value(TEXT_ATT, "O'Value", "AB", description='"O\'Brien Desc"')

        self.assertEqual(get_desc(TEXT_ATT, "O'Value"), "O'Brien Desc")
        self.assertIsNone(get_desc(TEXT_ATT, "O'Missing"))


class TestWarehouseChecks(ReportTestCase):
    def test_duplicate_short_code_and_listing_serial(self):
        raw("Warehouse", name="_Test RIGPL O'WH 1", warehouse_name="O'WH 1", short_code="O'SC",
            listing_serial=9871, is_group=0)

        def doc(**values):
            return frappe._dict(dict(name="_Test RIGPL O'WH 2", is_subcontracting_warehouse=0, is_group=0,
                warehouse_type="Store", listing_serial=9872, short_code="O'SC2"), **values)

        warehouse_validation.validate(doc(), "validate")
        self.assertRaisesRegex(frappe.ValidationError, "Short Code", warehouse_validation.validate,
            doc(short_code="O'SC"), "validate")
        self.assertRaisesRegex(frappe.ValidationError, "Listing Serial", warehouse_validation.validate,
            doc(listing_serial=9871), "validate")


class TestPurchaseReceiptSte(ReportTestCase):
    def test_draft_and_submitted_not_cancelled(self):
        pr = "_Test RIGPL O'PR"
        draft = raw("Stock Entry", purchase_receipt_no=pr, docstatus=0)
        submitted = raw("Stock Entry", purchase_receipt_no=pr, docstatus=1)
        raw("Stock Entry", purchase_receipt_no=pr, docstatus=2)

        found = get_existing_ste(frappe._dict(name=pr), "validate")

        self.assertEqual(sorted(row[0] for row in found), sorted([draft, submitted]))


class TestMadeToOrderAttributes(ReportTestCase):
    def test_duplicate_throws(self):
        values = dict(sales_order="_Test RIGPL O'SO", sales_order_item="O'SOI", item_code="O'Item")
        raw(MTO, docstatus=0, **values)
        doc = frappe.get_doc(dict(doctype=MTO, name="_Test RIGPL O'MTO", attributes=[], **values))

        self.assertRaisesRegex(frappe.ValidationError, "Already Exists", doc.validate)

    def test_copy_attributes_from_another_spl_by_idx(self):
        source = raw(MTO, docstatus=1)
        for idx, (attribute, value) in ((2, ("Tool Type", "O'Drill")), (1, ("Base Material", "O'Metal"))):
            raw("Item Variant Attribute", parent=source, parenttype=MTO, parentfield="attributes", idx=idx,
                attribute=attribute, attribute_value=value, numeric_values=0)
        doc = frappe.get_doc(dict(doctype=MTO, name="_Test RIGPL O'MTO", reference_spl=source))

        doc.copy_attributes_from_another_spl()

        self.assertEqual([(d.attribute, d.attribute_value) for d in doc.attributes],
            [("Base Material", "O'Metal"), ("Tool Type", "O'Drill")])


DN_ITEM = "_Test RIGPL DN Stock Item"
DN_WH = "_Test RIGPL DN Warehouse"


def dn_with_rows(*rows, **values):
    items = [frappe._dict(idx=i + 1, item_code=item, warehouse=wh, qty=qty, stock_qty=qty, conversion_factor=1)
        for i, (item, wh, qty) in enumerate(rows)]
    doc = frappe._dict(doctype="Delivery Note", name="_Test DN", posting_date="2026-01-10",
        posting_time="10:00:00", is_return=0, items=items)
    doc.update(values)
    return doc


class TestDeliveryNoteStockCheck(ReportTestCase):
    def setUp(self):
        raw("Item", name=DN_ITEM, item_code=DN_ITEM, is_stock_item=1)
        raw("Bin", item_code=DN_ITEM, warehouse=DN_WH, actual_qty=10)

    def check(self, doc):
        with patch.object(frappe.db, "get_single_value", return_value=0):
            delivery_note.check_stock_available(doc)

    def test_rows_of_one_item_are_added_before_the_comparison(self):
        doc = dn_with_rows((DN_ITEM, DN_WH, 6), (DN_ITEM, DN_WH, 6))

        with self.assertRaisesRegex(NegativeStockError, "<td>1, 2</td>.*2.0 units short"):
            self.check(doc)

    def test_enough_stock_passes_in_two_queries(self):
        doc = dn_with_rows((DN_ITEM, DN_WH, 4), (DN_ITEM, DN_WH, 6))

        self.assert_queries(2, lambda: self.check(doc))

    def test_item_without_bin_is_short_by_the_full_quantity(self):
        with self.assertRaisesRegex(NegativeStockError, "<td>1</td>.*3.0 units short"):
            self.check(dn_with_rows((DN_ITEM, "_Test RIGPL No Warehouse", 3)))

    def test_every_short_pair_is_listed_with_its_rows(self):
        doc = dn_with_rows((DN_ITEM, DN_WH, 11), (DN_ITEM, "_Test RIGPL No Warehouse", 3), (DN_ITEM, DN_WH, 1))

        with self.assertRaises(NegativeStockError) as ctx:
            self.check(doc)

        message = frappe.local.message_log[-1] if frappe.local.message_log else str(ctx.exception)
        self.assertRegex(str(message), r"<td>1, 3</td>.*2.0 units short")
        self.assertRegex(str(message), r"<td>2</td>.*3.0 units short")

    def test_return_and_negative_stock_setting_skip_the_check(self):
        self.check(dn_with_rows((DN_ITEM, DN_WH, 99), is_return=1))
        with patch.object(frappe.db, "get_single_value", return_value=1):
            delivery_note.check_stock_available(dn_with_rows((DN_ITEM, DN_WH, 99)))

    def test_validate_checks_stock_only_on_submit(self):
        names = ["check_draft_dn", "get_linked_so_data", "check_strict_po_rules", "copy_address_and_check",
            "copy_so_price_lists", "check_sales_order_rows", "check_reconciliations"]
        names.append("validate_made_to_order_items")
        patches = [patch.object(delivery_note, name) for name in names]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        doc = dn_with_rows((DN_ITEM, DN_WH, 99))
        with patch.object(delivery_note, "check_stock_available") as check:
            delivery_note.validate(doc, "validate")
            check.assert_not_called()
            doc._action = "submit"
            delivery_note.validate(doc, "validate")
            check.assert_called_once_with(doc)
            delivery_note.validate_made_to_order_items.assert_called_once_with(doc)

    def test_shortfalls_use_one_query(self):
        pairs = {(DN_ITEM, DN_WH): 15, (DN_ITEM, "_Test RIGPL No Warehouse"): 0, (DN_ITEM, None): 5}

        shortfalls = self.assert_queries(1, lambda: get_stock_shortfalls(pairs))

        self.assertEqual(shortfalls, {(DN_ITEM, DN_WH): 5})

