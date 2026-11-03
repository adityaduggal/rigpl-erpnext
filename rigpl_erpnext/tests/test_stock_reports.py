"""
Stock and Item reports after the move from '%s' SQL to frappe.qb (#187). Each filter value has a
quote: the old reports put it into the SQL text and failed.
"""
import frappe

from rigpl_erpnext.rigpl_erpnext.report.item_template import item_template
from rigpl_erpnext.rigpl_erpnext.report.standards_and_drawings_rigpl import standards_and_drawings_rigpl
from rigpl_erpnext.rigpl_erpnext.report.stock_status import stock_status
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw
from rigpl_erpnext.tests.test_variant_table import insert_item

BM = "_Test RIGPL O'Metal"
TT = "_Test RIGPL O'Drill"
ITEM = "_Test RIGPL O'Brien Stock Item"
ITEM_2 = "_Test RIGPL O'Brien Stock Item 2"
RM_ITEM = "_Test RIGPL O'Brien Stock RM"
TEMPLATE = "_Test RIGPL O'Brien Stock Template"
CUSTOMER = "_Test RIGPL O'Brien Customer"


def insert_stock_item(name, d1, extra=()):
    insert_item(name, variant_of=TEMPLATE, attributes=[("Base Material", BM), ("Tool Type", TT), ("d1_mm", d1),
        *extra])
    frappe.db.set_value("Item", name, {"is_sales_item": 1}, update_modified=False)


def insert_bin(item_code, warehouse, actual=0, ordered=0, planned=0, reserved=0):
    raw("Bin", item_code=item_code, warehouse=warehouse, actual_qty=actual, ordered_qty=ordered, planned_qty=planned,
        reserved_qty=reserved)


class TestStandardsAndDrawings(ReportTestCase):
    def test_drawing_filters(self):
        mine = raw("Important Documents", type="Drawing", drawing_based_on="Customer", customer=CUSTOMER,
            sales_order="_Test RIGPL O'SO", docstatus=1)
        raw("Important Documents", type="Drawing", drawing_based_on="Customer", customer=CUSTOMER, docstatus=1)

        # based_on raised NameError, sales_order compared the customer
        data = self.assert_queries(1, lambda: standards_and_drawings_rigpl.execute(frappe._dict(type="Drawing",
            based_on="Customer", customer=CUSTOMER, sales_order="_Test RIGPL O'SO"))[1])

        self.assertEqual([row[0] for row in data], [mine])

    def test_standard_number_pattern_and_type(self):
        std = raw("Important Documents", type="Standard", standard_number="_Test O'DIN 338", category_name="O'Cat")

        data = standards_and_drawings_rigpl.execute(frappe._dict(type="Standard", std_no="%O'DIN%",
            category="O'Cat"))[1]

        self.assertEqual([row[0] for row in data], [std])
        self.assertRaises(frappe.ValidationError, standards_and_drawings_rigpl.execute, frappe._dict(type=""))


class TestStockStatus(ReportTestCase):
    def test_stock_sums_and_rm_excluded(self):
        insert_stock_item(ITEM, "6", extra=[("Number of Flutes Zn", "4")])
        insert_stock_item(ITEM_2, "3")
        insert_stock_item(RM_ITEM, "1", extra=[("Is RM", "Yes")])
        insert_bin(ITEM, "BGH655 - RIGPL", actual=5, ordered=2)
        insert_bin(ITEM, "_Test RIGPL O'WH", actual=3, ordered=1, planned=1)
        insert_bin(ITEM_2, "Dead Stock - RIGPL", actual=1)
        insert_bin(RM_ITEM, "BGH655 - RIGPL", actual=9)
        # 2 reorder rows multiplied the old sums
        for idx in (1, 2):
            raw("Item Reorder", parent=ITEM, parenttype="Item", parentfield="reorder_levels", idx=idx)

        data = self.assert_queries(4, lambda: stock_status.execute(frappe._dict(bm=BM, tt=TT))[1])

        self.assertEqual([row[0] for row in data], [ITEM_2, ITEM])
        self.assertEqual((data[1][10], data[1][15]), (6, 4))
        self.assertEqual(data[1][17:], [5, 5, 2])


class TestItemTemplate(ReportTestCase):
    def test_restrictions_counts_and_hidden_rows(self):
        insert_item(TEMPLATE)
        for idx, (attribute, value) in enumerate((("Base Material", BM), ("Tool Type", TT), ("Type Selector", "A"),
                ("Type Selector", "B")), start=1):
            raw("Item Variant Restrictions", parent=TEMPLATE, parenttype="Item", parentfield="item_variant_restrictions",
                idx=idx, attribute=attribute, allowed_values=value)
        insert_stock_item(ITEM, "6")
        raw("Website Item", item_code=ITEM, variant_of=TEMPLATE, published=1)

        data = self.assert_queries(5, lambda: item_template.execute(frappe._dict(bm=BM, tt=TT))[1])

        # The 2 Type Selector rows doubled the old row
        self.assertEqual([(row[0], row[1], row[4], row[8], row[18]) for row in data], [(TEMPLATE, 1, BM, TT, 1)])
