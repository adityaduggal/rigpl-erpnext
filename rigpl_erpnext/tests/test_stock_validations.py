"""
Item, Warehouse, Purchase Receipt and Made to Order validations after the move from '%s' SQL to
parameters (#187). Each name or value has a quote: the old code put it into the SQL text and failed.
"""
import frappe
from rohit_common.utils.rohit_common_utils import fn_check_digit

from rigpl_erpnext.rigpl_erpnext.validations import warehouse as warehouse_validation
from rigpl_erpnext.rigpl_erpnext.validations.item import generate_item_code
from rigpl_erpnext.rigpl_erpnext.validations.purchase_receipt import get_existing_ste
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw
from rigpl_erpnext.utils.item_utils import get_desc

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
