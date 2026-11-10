"""
Label Printing Database RIGPL (#214): the same rows as the old 26 join query, 2 queries for any number
of items, and only the Items that the user can read.
"""
import frappe

from rigpl_erpnext.rigpl_erpnext.report.label_printing_database_rigpl import label_printing_database_rigpl as report
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw
from rigpl_erpnext.tests.test_variant_table import insert_item

USER = "_test_rigpl_label_report@example.com"
HSS, CARBIDE, PLAIN, ZERO = (
    "_Test RIGPL Label HSS", "_Test RIGPL Label Carbide", "_Test RIGPL Label Plain", "_Test RIGPL Label Zero")
ITEMS = (HSS, CARBIDE, PLAIN, ZERO)


class TestLabelPrintingReport(ReportTestCase):
    def setUp(self):
        insert_item(HSS, variant_of="_Test RIGPL Label Template", attributes=[
            ("Base Material", "HSS"), ("HSS Quality", "H-2X"), ("Tool Type", "Drill"), ("Brand", "None"),
            ("Special Treatment", "ACX"), ("d1_inch", "3/32"), ("d1_mm", "2.4"), ("l1_mm", "50"),
            ("Number of Flutes Zn", "2")])
        insert_item(CARBIDE, variant_of="_Test RIGPL Label Template", attributes=[
            ("Base Material", "Carbide"), ("Carbide Quality", "C-K10"), ("Special Treatment", "TiN"),
            ("d1_mm", "6"), ("w1_mm", "3"), ("l1_mm", "50"), ("r1_mm", "0.5"), ("l3_mm", "20")])
        insert_item(PLAIN, variant_of="_Test RIGPL Label Template")
        insert_item(ZERO, variant_of="_Test RIGPL Label Template", attributes=[
            ("d1_mm", "6"), ("l1_mm", "0"), ("d2_mm", "0.000"), ("r1_mm", "0")])
        for item in ITEMS:
            frappe.db.set_value("Item", item, "is_sales_item", 1)

    def rows(self):
        return {row[0]: row for row in report.execute()[1] if row[0] in ITEMS}

    def test_hss_base_material_and_special_treatment(self):
        row = self.rows()[HSS]
        self.assertEqual(row[1], "HSS-M35")
        self.assertEqual(row[2], "")  # brand 'None'
        self.assertEqual(row[3], "2X")
        self.assertEqual(row[7], "2X Nova")  # ACX is sold as Nova

    def test_inch_before_mm_and_label_desc(self):
        row = self.rows()[HSS]
        self.assertEqual(row[8:10], ["3/32", "''"])
        self.assertEqual(row[12:14], ["50", ""])
        self.assertEqual(row[18], "Z2")
        self.assertEqual(row[19], "3/32''x50")
        carbide = self.rows()[CARBIDE]
        self.assertEqual(carbide[19], "CR:0.5 6x3x50 RL:20")
        self.assertEqual(carbide[7], "K10 TiN")

    def test_label_desc_is_column_20(self):
        columns = report.get_columns()
        self.assertEqual(columns[19]["label"], "Label Desc")
        self.assertEqual(len(columns), len(self.rows()[HSS]))

    def test_item_without_attributes_shows(self):
        row = self.rows()[PLAIN]
        self.assertEqual(row[8], "")
        self.assertEqual(row[19], "")

    def test_zero_sizes_are_blank(self):
        row = self.rows()[ZERO]
        self.assertIsNone(row[12])  # l1 0
        self.assertIsNone(row[14])  # d2 0.000
        self.assertIsNone(row[21])  # r1 0
        self.assertEqual(row[19], "6")

    def test_query_count_does_not_depend_on_items(self):
        self.assert_queries(12, report.execute)

    def test_user_sees_only_permitted_items(self):
        raw("User", name=USER, email=USER, first_name="_Test RIGPL Label", user_type="System User", enabled=1)
        raw("Has Role", parent=USER, parenttype="User", parentfield="roles", role="Stock User")
        frappe.clear_cache(user=USER)
        frappe.get_doc(dict(doctype="User Permission", user=USER, allow="Item", for_value=HSS,
            apply_to_all_doctypes=1)).insert(ignore_permissions=True)
        frappe.set_user(USER)
        names = {row[0] for row in report.execute()[1]}
        self.assertEqual(names, {HSS})
