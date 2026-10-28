
import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.rigpl_erpnext.report.item_report_rigpl import item_report_rigpl as report


def meta(numeric=0, hidden=0):
    return frappe._dict(numeric_values=numeric, hidden=hidden, max_length=0)


class TestItemReportLabels(FrappeTestCase):
    def test_first_field_name_like_sql_group_by(self):
        self.assertIsNone(report.first_field_name({"Dia (mm)", None}))
        names = {"flute Dia (mm)", "Body Dia (mm)"}
        self.assertEqual(report.first_field_name(names), "Body Dia (mm)")

    def test_label_for_numeric_attribute_uses_field_name_and_unit(self):
        label = report.get_name_in_template("d1_mm", meta(1), "Flute Dia (inch)")
        self.assertEqual(label, "Flute Dia (mm)")
        self.assertEqual(report.get_name_in_template("d1_mm", meta(1), None), "d1_mm")

    def test_label_for_text_attribute(self):
        self.assertEqual(report.get_name_in_template("Brand", meta(), "Brand"), "Brand")
        self.assertEqual(
            report.get_name_in_template("Coolant_Holes", meta(hidden=1), "Coolant (Yes)"),
            "Coolant (Holes)",
        )

    def test_attribute_filter_values(self):
        values = report.get_attribute_values({"bm": "HSS", "quality": "H-1X", "tt": "Drill"})

        self.assertEqual(values["HSS Quality"], "H-1X")
        self.assertEqual(values["Tool Type"], "Drill")
        self.assertIsNone(values["Series"])
