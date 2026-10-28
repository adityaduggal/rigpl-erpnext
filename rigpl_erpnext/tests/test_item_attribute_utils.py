import unittest

import frappe

from rigpl_erpnext.utils import item_attribute_utils as iau
from rigpl_erpnext.utils.item_utils import get_item_attributes

TEXT_ATT = "_Test IAU Material"
NUM_ATT = "_Test IAU d1_mm"
ITEM_1 = "_Test IAU Item 1"
ITEM_2 = "_Test IAU Item 2"
MTO = "Made to Order Item Attributes"


def add_attribute_row(parent, attribute, value, idx, parenttype="Item"):
    frappe.get_doc(
        doctype="Item Variant Attribute",
        name=frappe.generate_hash(length=10),
        parent=parent,
        parenttype=parenttype,
        parentfield="attributes",
        idx=idx,
        attribute=attribute,
        attribute_value=value,
    ).db_insert()


def add_item_attribute(name, numeric, values=()):
    frappe.get_doc(
        doctype="Item Attribute", name=name, attribute_name=name, numeric_values=numeric
    ).db_insert()
    for idx, value in enumerate(values, 1):
        frappe.get_doc(
            doctype="Item Attribute Value",
            name=frappe.generate_hash(length=10),
            parent=name,
            parenttype="Item Attribute",
            parentfield="item_attribute_values",
            idx=idx,
            attribute_value=value,
            abbr=value,
        ).db_insert()


class TestAttributeSortKey(unittest.TestCase):
    def test_sorts_like_sql_order_by(self):
        rows = {
            "a": {TEXT_ATT: "hss", NUM_ATT: "10"},
            "b": {TEXT_ATT: "Carbide", NUM_ATT: "2.5"},
            "c": {TEXT_ATT: "HSS", NUM_ATT: "2"},
            "d": {NUM_ATT: "99"},
        }
        def key(name):
            return iau.attribute_sort_key(rows[name], [TEXT_ATT, NUM_ATT], {NUM_ATT})

        order = sorted(rows, key=key)

        # No value first, text without case, numbers by value ("10" after "2").
        self.assertEqual(order, ["d", "b", "c", "a"])

    def test_chunks_are_distinct_and_small(self):
        self.assertEqual(list(iau.chunks(["a", "b", "a", "c"], size=2)), [["a", "b"], ["c"]])


class TestAttributeQueries(unittest.TestCase):
    def setUp(self):
        add_attribute_row(ITEM_1, TEXT_ATT, "HSS", 1)
        add_attribute_row(ITEM_1, NUM_ATT, "6", 2)
        add_attribute_row(ITEM_2, TEXT_ATT, "Carbide", 1)
        add_attribute_row(ITEM_2, NUM_ATT, "6", 2)
        # A Made to Order Item Attributes row with an item's name must not count.
        add_attribute_row(ITEM_2, TEXT_ATT, "HSS", 1, parenttype=MTO)

    def tearDown(self):
        frappe.db.rollback()

    def test_attribute_map(self):
        att_map = iau.get_attribute_map([ITEM_1, ITEM_2, "_Test IAU No Rows"])

        self.assertEqual(
            att_map,
            {
                ITEM_1: {TEXT_ATT: "HSS", NUM_ATT: "6"},
                ITEM_2: {TEXT_ATT: "Carbide", NUM_ATT: "6"},
            },
        )
        self.assertEqual(
            iau.get_attribute_map([ITEM_1], [NUM_ATT]), {ITEM_1: {NUM_ATT: "6"}}
        )
        self.assertEqual(iau.get_attribute_map([ITEM_1], []), {})

    def test_attribute_filters(self):
        item = frappe.qb.DocType("Item Variant Attribute")
        candidates = item.parent.isin([ITEM_1, ITEM_2])

        def matching(values):
            criterion = iau.attribute_filters(item.parent, values) & candidates
            query = frappe.qb.from_(item).select(item.parent).where(criterion)
            return sorted({row[0] for row in query.run()})

        self.assertEqual(matching({TEXT_ATT: "HSS"}), [ITEM_1])
        self.assertEqual(matching({TEXT_ATT: "HSS", NUM_ATT: "6"}), [ITEM_1])
        self.assertEqual(matching({NUM_ATT: "6", TEXT_ATT: None}), [ITEM_1, ITEM_2])

    def test_item_attributes_shim_keeps_row_shape(self):
        rows = get_item_attributes(ITEM_1)

        self.assertEqual(
            [(r.idx, r.attribute, r.attribute_value) for r in rows],
            [(1, TEXT_ATT, "HSS"), (2, NUM_ATT, "6")],
        )
        self.assertEqual(set(rows[0]), set(iau.ROW_FIELDS))

    def test_attribute_meta(self):
        add_item_attribute(TEXT_ATT, 0, values=["HSS", "Carbide"])
        add_item_attribute(NUM_ATT, 1)

        meta = iau.get_attribute_meta([TEXT_ATT, NUM_ATT])

        self.assertEqual(meta[TEXT_ATT].max_length, len("Carbide"))
        self.assertEqual((meta[NUM_ATT].numeric_values, meta[NUM_ATT].max_length), (1, 0))
