import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.validations import stock_entry, stock_reconciliation as sr
from rigpl_erpnext.tests.test_variant_table import insert_item

ROD = "_Test RIGPL VR Rod 330"
CUT = "_Test RIGPL VR Cut 150"
TEMPLATE = "_Test RIGPL VR Template"
TOOL = "_Test RIGPL VR Tool"


def sr_row(qty, current_qty, current_rate, item_code=ROD, warehouse="_Test RIGPL WH", manual=0,
        rate=0):
    return frappe._dict(item_code=item_code, warehouse=warehouse, qty=qty, current_qty=current_qty,
        current_valuation_rate=current_rate, valuation_rate=rate, manual_valuation_rate=manual)


class FakeDoc:
    """A document stand-in. frappe._dict cannot hold `items`, since dict.items wins."""
    def __init__(self, items):
        self.items = items

    def get(self, key):
        return getattr(self, key)


class FakeSR(FakeDoc):
    def set_total_qty_and_amount(self):
        for d in self.items:
            d.amount = d.qty * d.valuation_rate
            d.amount_difference = d.amount - d.current_qty * d.current_valuation_rate


def ste_row(item_code, qty, s_warehouse=None, t_warehouse=None, basic_rate=0):
    return frappe._dict(item_code=item_code, qty=qty, s_warehouse=s_warehouse,
        t_warehouse=t_warehouse, basic_rate=basic_rate, amount=qty * basic_rate)


def warm_meta_cache(run_once):
    """Runs a hook once so the guard does not count the first DocType meta and column loads."""
    run_once()


class TestSRBookRate(FrappeTestCase):
    def test_qty_down_or_same_keeps_current_rate(self):
        self.assertEqual(sr.get_book_rate(sr_row(5, 8, 100), 450), 100)
        self.assertEqual(sr.get_book_rate(sr_row(8, 8, 100), 450), 100)
        self.assertEqual(sr.get_book_rate(sr_row(0, 8, 100), 450), 100)

    def test_qty_up_values_only_extra_at_item_rate(self):
        self.assertEqual(sr.get_book_rate(sr_row(10, 8, 100), 450), 170)

    def test_no_current_stock_uses_item_rate(self):
        self.assertEqual(sr.get_book_rate(sr_row(10, 0, 0), 450), 450)
        self.assertEqual(sr.get_book_rate(sr_row(10, -3, 100), 450), 450)
        self.assertEqual(sr.get_book_rate(sr_row(10, 5, 0), 450), 450)

    def test_warehouse_rules(self):
        self.assertEqual(sr.apply_warehouse_rule(170, None), 170)
        self.assertEqual(sr.apply_warehouse_rule(170, frappe._dict(valuation_rule="")), 170)
        fixed = frappe._dict(valuation_rule="Fixed Rate", valuation_rule_value=1)
        self.assertEqual(sr.apply_warehouse_rule(170, fixed), 1)
        pct = frappe._dict(valuation_rule="Percent of Rate", valuation_rule_value=25)
        self.assertEqual(sr.apply_warehouse_rule(1000, pct), 250)


class TestValuationHooks(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        insert_item(TEMPLATE)
        insert_item(ROD, variant_of=TEMPLATE, attributes=[("l1_mm", "330")])
        insert_item(CUT, variant_of=TEMPLATE, attributes=[("l1_mm", "150")])
        insert_item(TOOL)
        for name, vr, purchase in ((ROD, 16680, 1), (CUT, 6060, 1), (TOOL, 6900, 0)):
            frappe.db.set_value("Item", name, {"valuation_rate": vr, "is_purchase_item": purchase})

    def test_sr_validate(self):
        doc = FakeSR([
            sr_row(10, 8, 100),
            sr_row(8, 8, 100, item_code=CUT),
            sr_row(3, 1, 100, manual=1, rate=77),
        ])
        warm_meta_cache(lambda: sr.validate(FakeSR([sr_row(1, 1, 1)]), "validate"))
        with assert_max_queries(2, test_case=self):
            sr.validate(doc, "validate")
        self.assertEqual([d.valuation_rate for d in doc.items], [(800 + 2 * 16680) / 10, 100, 77])
        self.assertEqual(doc.difference_amount, (800 + 2 * 16680 - 800) + 0 + (3 * 77 - 100))

    def test_ste_cut_piece_gets_rod_rate(self):
        ste = FakeDoc([
            ste_row(ROD, 2, s_warehouse="RM", basic_rate=4350),
            ste_row(CUT, 2, t_warehouse="RM"),
            ste_row(TOOL, 2, t_warehouse="RG"),
        ])
        warm_meta_cache(lambda: stock_entry.update_valuation_rate(FakeDoc([ste_row(TOOL, 1)])))
        with assert_max_queries(2, test_case=self):
            stock_entry.update_valuation_rate(ste)
        self.assertAlmostEqual(ste.items[1].basic_rate, 4350 * 150 / 330 * 0.8)
        self.assertEqual(ste.items[2].basic_rate, 6900)

    def test_ste_without_rod_uses_item_rate(self):
        ste = FakeDoc([ste_row(CUT, 2, t_warehouse="RM")])
        stock_entry.update_valuation_rate(ste)
        self.assertEqual(ste.items[0].basic_rate, 6060)

    def test_ste_same_item_in_and_out_keeps_rate(self):
        ste = FakeDoc([
            ste_row(CUT, 1, s_warehouse="RM", basic_rate=1200),
            ste_row(CUT, 1, t_warehouse="RM"),
        ])
        stock_entry.update_valuation_rate(ste)
        self.assertEqual(ste.items[1].basic_rate, 1200)

    def test_ste_shorter_source_is_not_a_rod(self):
        ste = FakeDoc([
            ste_row(CUT, 1, s_warehouse="RM", basic_rate=1200),
            ste_row(ROD, 1, t_warehouse="RM"),
        ])
        stock_entry.update_valuation_rate(ste)
        self.assertEqual(ste.items[1].basic_rate, 16680)
