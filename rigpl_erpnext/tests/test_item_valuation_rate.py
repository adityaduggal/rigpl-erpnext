import datetime

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.scheduled_tasks import item_valuation_rate as ivr
from rigpl_erpnext.tests.test_variant_table import insert_item

D1 = datetime.date(2025, 1, 1)
D2 = datetime.date(2026, 1, 1)
PURCHASE = frappe._dict(is_sales_item=0, is_purchase_item=1)
CARBIDE = {"Base Material": "Carbide", "Tool Type": "Round Tool Bits"}


def item(vr, vr_date=None, name="IT"):
    return frappe._dict(name=name, valuation_rate=vr, valuation_rate_date=vr_date, disabled=0)


def rod(name, dia, length):
    return name, dict(CARBIDE, d1_mm=dia, l1_mm=length)


class TestNewValuation(FrappeTestCase):
    def test_older_price_is_ignored(self):
        self.assertIsNone(ivr.get_new_valuation(item(100, D2), 500, PURCHASE, D1))

    def test_rate_outside_10_percent_changes(self):
        self.assertEqual(ivr.get_new_valuation(item(100, D1), 500, PURCHASE, D2),
            {"valuation_rate": 500, "valuation_rate_date": D2})

    def test_rate_within_10_percent_changes_only_date(self):
        self.assertEqual(ivr.get_new_valuation(item(100, D1), 105, PURCHASE, D2),
            {"valuation_rate": 100, "valuation_rate_date": D2})
        self.assertIsNone(ivr.get_new_valuation(item(100, D2), 105, PURCHASE, D2))


class TestCutPcRate(FrappeTestCase):
    def setUp(self):
        self.attributes = dict([rod("CUT", "8.2", "50"), rod("R60", "8.2", "60"),
            rod("R100", "8", "100"), rod("R40", "8.2", "40"), rod("D10", "10", "330")])
        self.variants = [frappe._dict(name=n) for n in self.attributes]

    def test_latest_longer_rod_of_near_diameter(self):
        pp = {"R60": (300, D1), "R100": (1000, D2), "R40": (100, D2), "D10": (5000, D2)}
        rate, pur_date = ivr.get_cut_pc_rate("CUT", self.variants, self.attributes, pp)
        self.assertEqual((rate, pur_date), (1000 * 50 / 100 * 0.8, D2))

    def test_same_date_takes_shortest_longer_rod(self):
        pp = {"R60": (300, D2), "R100": (1000, D2)}
        rate, _date = ivr.get_cut_pc_rate("CUT", self.variants, self.attributes, pp)
        self.assertEqual(rate, 300 * 50 / 60 * 0.9)

    def test_no_purchase_or_not_carbide(self):
        self.assertIsNone(ivr.get_cut_pc_rate("CUT", self.variants, self.attributes, {}))
        self.attributes["CUT"]["Base Material"] = "HSS"
        self.assertIsNone(ivr.get_cut_pc_rate("CUT", self.variants, self.attributes, {}))


class TestTemplateQueries(FrappeTestCase):
    def test_fixed_queries_per_template(self):
        template = "_Test RIGPL IVR Template"
        insert_item(template)
        for idx in range(5):
            insert_item(f"{template} {idx}", variant_of=template,
                attributes=[("Base Material", "Carbide"), ("l1_mm", str(50 + idx))])
        tmpl = frappe._dict(name=template, is_sales_item=0, is_purchase_item=1)
        ivr.get_template_changes(tmpl, None)  # first DocType meta and column loads
        with assert_max_queries(3, test_case=self):
            self.assertEqual(ivr.get_template_changes(tmpl, None), {})
