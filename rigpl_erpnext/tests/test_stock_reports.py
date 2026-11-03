"""
Stock and Item reports after the move from '%s' SQL to frappe.qb (#187). Each filter value has a
quote: the old reports put it into the SQL text and failed.
"""
import frappe

from rigpl_erpnext.rigpl_erpnext.report.dealer_stock_status import dealer_stock_status
from rigpl_erpnext.rigpl_erpnext.report.item_lead_times import item_lead_times
from rigpl_erpnext.rigpl_erpnext.report.item_template import item_template
from rigpl_erpnext.rigpl_erpnext.report.standards_and_drawings_rigpl import standards_and_drawings_rigpl
from rigpl_erpnext.rigpl_erpnext.report.stock_status import stock_status
from rigpl_erpnext.rigpl_erpnext.report.template_variant_import_format import template_variant_import_format
from rigpl_erpnext.rigpl_erpnext.report.valuation_rate import valuation_rate
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw
from rigpl_erpnext.tests.test_variant_table import insert_item, insert_item_price

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


class TestTemplateVariantImportFormat(ReportTestCase):
    def test_variants_and_restrictions_need_templates(self):
        insert_item(TEMPLATE)
        insert_stock_item(ITEM, "6")

        data = template_variant_import_format.execute(frappe._dict(variant_of="O'Brien Stock Template"))[1]

        self.assertEqual({row[0] for row in data}, {ITEM})
        self.assertRaises(frappe.ValidationError, template_variant_import_format.execute,
            frappe._dict(restrictions=1, template=0))


class TestDealerStockStatus(ReportTestCase):
    def test_ready_reserved_and_total(self):
        raw("Warehouse", name="_Test RIGPL O'FG WH", warehouse_name="O'FG", short_code="_TOFG", listing_serial=99,
            warehouse_type="Finished Stock", is_group=0, disabled=0, is_subcontracting_warehouse=0)
        insert_stock_item(ITEM, "6")
        insert_bin(ITEM, "_Test RIGPL O'FG WH", actual=4, reserved=1)

        data = self.assert_queries(6, lambda: dealer_stock_status.execute(frappe._dict(bm=BM, tt=TT))[1])

        row = next(row for row in data if row[0] == ITEM)
        self.assertEqual(row[5], 6)
        self.assertEqual(row[-4:], [4, None, 1, 3])


class TestItemLeadTimes(ReportTestCase):
    def test_summary_attributes_and_detail_needs_item(self):
        insert_stock_item(ITEM, "6")
        filters = frappe._dict(from_date="2026-01-01", to_date="2026-10-31", bm=BM, tt=TT)

        data = item_lead_times.execute(filters)[1]

        self.assertEqual([(row[0], row[10], row[13], row[15]) for row in data], [(ITEM, BM, TT, 6)])
        # Neither manufactured nor purchased: the old report failed with KeyError no_of_trans
        frappe.db.set_value("Item", ITEM, {"include_item_in_manufacturing": 0, "is_purchase_item": 0},
            update_modified=False)
        self.assertEqual(item_lead_times.execute(filters)[1][0][2:5], ["Unknown", 0, 0])
        self.assertRaises(frappe.ValidationError, item_lead_times.execute, frappe._dict(filters, detail=1))


class TestValuationRate(ReportTestCase):
    def test_price_rows_percent_and_attribute_sort(self):
        insert_item(TEMPLATE, attributes=[("Base Material", ""), ("Tool Type", ""), ("d1_mm", "")])
        # The label takes the field name of the template row and the unit of the attribute name
        iva = frappe.qb.DocType("Item Variant Attribute")
        frappe.qb.update(iva).set(iva.field_name, "Flute Dia (inch)").where(
            (iva.parent == TEMPLATE) & (iva.attribute == "d1_mm")).run()
        insert_stock_item(ITEM, "6")
        insert_stock_item(ITEM_2, "3")
        frappe.db.set_value("Item", ITEM, {"valuation_rate": 50}, update_modified=False)
        insert_item_price(ITEM, 200, price_list="_Test RIGPL O'PL")
        insert_item_price(ITEM, 999, price_list="_Test RIGPL Other PL")
        filters = frappe._dict(pl="_Test RIGPL O'PL", eol="2026-01-01", bm=BM, tt=TT)

        columns, data = self.assert_queries(6, lambda: valuation_rate.execute(filters))

        labels = [column.split(":")[0] for column in columns]
        self.assertEqual(labels[7:10], ["Base Material", "Tool Type", "Flute Dia (mm)"])
        # Sorted by d1_mm as a number; an item with no price has empty price cells
        self.assertEqual([row[:6] for row in data], [
            [ITEM_2, None, None, None, None, None],
            [ITEM, 50, None, "_Test RIGPL O'PL", 200, 25],
        ])
        self.assertEqual(data[0][7:10], [BM, TT, 3])
        self.assertRaises(frappe.ValidationError, valuation_rate.execute, frappe._dict(filters, bm="O'None"))
