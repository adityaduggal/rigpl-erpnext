"""
Stock and Item reports after the move from '%s' SQL to frappe.qb (#187). Each filter value has a
quote: the old reports put it into the SQL text and failed.
"""
import frappe

from rigpl_erpnext.rigpl_erpnext.report.standards_and_drawings_rigpl import standards_and_drawings_rigpl
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
