from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_months

from rigpl_erpnext.tests.test_variant_table import insert_item
from rigpl_erpnext.utils.stock_utils import (
    cancel_delete_ste_from_name,
    compute_rol_for_items,
    get_existing_rol_for_item,
    get_consumption_rol,
    get_max_lead_times,
    get_sales_rol,
    has_regular_consumption,
    limit_rol_change,
)

# The quotes would break the old '%s' queries
TEMPLATE = "_Test RIGPL O'Brien Template"
VARIANT = "_Test RIGPL O'Brien Variant"
OTHER_VARIANT = "_Test RIGPL O'Brien Variant 2"
DISABLED_VARIANT = "_Test RIGPL O'Brien Variant 3"


def set_lead_time(item_code, days):
    frappe.db.set_value("Item", item_code, "lead_time_days", days, update_modified=False)


class TestStockUtilsQueries(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_existing_rol_reads_item_with_quote(self):
        insert_item(VARIANT, variant_of=TEMPLATE)
        frappe.get_doc(
            doctype="Item Reorder", name=frappe.generate_hash(length=10), parent=VARIANT,
            parenttype="Item", parentfield="reorder_levels", idx=1, warehouse_reorder_level=25,
        ).db_insert()

        self.assertEqual(get_existing_rol_for_item(VARIANT), 25)
        self.assertEqual(get_existing_rol_for_item("_Test RIGPL No Such Item"), 0)

    def test_max_lead_time_of_enabled_sister_variants(self):
        insert_item(TEMPLATE)
        insert_item(VARIANT, variant_of=TEMPLATE)
        insert_item(OTHER_VARIANT, variant_of=TEMPLATE)
        insert_item(DISABLED_VARIANT, variant_of=TEMPLATE, disabled=1)
        set_lead_time(OTHER_VARIANT, 12)
        set_lead_time(DISABLED_VARIANT, 40)

        self.assertEqual(get_max_lead_times(VARIANT), 12)
        self.assertEqual(get_max_lead_times(TEMPLATE), 0)

    def test_cancel_delete_ste_deletes_its_ledger_entries(self):
        ste_name = "_Test RIGPL STE O'Brien"
        frappe.get_doc(doctype="Stock Entry", name=ste_name, docstatus=0,
            stock_entry_type="Material Receipt", purpose="Material Receipt").db_insert()
        for _ in range(2):
            frappe.get_doc(doctype="Stock Ledger Entry", name=frappe.generate_hash(length=10),
                voucher_type="Stock Entry", voucher_no=ste_name, docstatus=1).db_insert()

        cancel_delete_ste_from_name(ste_name)

        self.assertFalse(frappe.db.exists("Stock Entry", ste_name))
        self.assertFalse(frappe.get_all("Stock Ledger Entry", filters={"voucher_no": ste_name}))


TO_DATE = date(2026, 11, 1)
ITEM = "_Test RIGPL Rare"


def make_item(existing_rol=32):
    return frappe._dict(name=ITEM, valuation_rate=1000, lead_time_days=30, existing_rol=existing_rol,
        is_sales_item=1)


def make_lines(count, customers=1, qty=10):
    return [frappe._dict(sales_order=f"SO-{i}", customer=f"C{i % customers}", stock_qty=qty,
        transaction_date=date(2026, 5, 1)) for i in range(count)]


def make_consumption(ste_6=0, ste_12=0):
    """Consumption windows as get_consumption_by_window returns them"""
    def window(count):
        return {ITEM: frappe._dict(qty=10 * count, no_of_ste=count)} if count else {}
    return {6: window(ste_6), 12: window(ste_12), 24: window(ste_12)}


def make_con_lines(count, qty=10):
    """Consumption of count Stock Entries, 1 each week of the last months"""
    return {ITEM: [(add_days(TO_DATE, -7 * (i + 1)), qty) for i in range(count)]}


def compute(itm, order_lines, consumption, consumption_lines=None):
    return compute_rol_for_items([itm], to_date=TO_DATE, consumption=consumption,
        order_lines={ITEM: order_lines} if order_lines else {},
        consumption_lines=consumption_lines or {})[ITEM]


class TestRareItemRol(FrappeTestCase):
    """Seldom-used sales items get no ROL (#219)"""

    def test_rare_item_gets_zero_rol(self):
        new_rol, basis, ch_type = compute(make_item(), make_lines(2), make_consumption())
        self.assertEqual(new_rol, 0)
        self.assertEqual(ch_type, "decrease")
        self.assertIn("Rare", basis)
        self.assertIn("no ROL", basis)

    def test_item_with_few_orders_from_few_customers_gets_zero_rol(self):
        # 12 orders would be Occasional, but all from 1 customer
        new_rol, _basis, _ch = compute(make_item(), make_lines(12, customers=1),
            make_consumption())
        self.assertEqual(new_rol, 0)

    def test_item_with_many_orders_from_few_customers_is_not_rare(self):
        # 13 orders from 2 customers is a Regular item
        _rol, basis, is_rare = get_sales_rol(make_item(), make_lines(13, customers=2), TO_DATE)
        self.assertFalse(is_rare)
        self.assertIn("Regular", basis)

    def test_limits_do_not_keep_old_rol_of_rare_item(self):
        # The change limits would stop 32 from falling to 0
        itm = make_item(existing_rol=32)
        self.assertEqual(limit_rol_change(itm, 0, "Rare", True), (0, "Rare", "decrease"))
        self.assertEqual(limit_rol_change(make_item(0), 0, "Rare", True), (0, "Rare", "same"))

    def test_occasional_item_is_not_rare(self):
        _rol, basis, is_rare = get_sales_rol(make_item(), make_lines(5, customers=5), TO_DATE)
        self.assertFalse(is_rare)
        self.assertIn("Occasional", basis)


class TestConsumptionRol(FrappeTestCase):
    """Consumption with Stock Entries adds to the ROL (#219)"""

    def test_consumption_needs_more_than_3_entries_in_6_months(self):
        self.assertFalse(has_regular_consumption(ITEM, make_consumption(ste_6=3)))
        self.assertTrue(has_regular_consumption(ITEM, make_consumption(ste_6=4)))

    def test_consumption_needs_more_than_6_entries_in_12_months(self):
        self.assertFalse(has_regular_consumption(ITEM, make_consumption(ste_12=6)))
        self.assertTrue(has_regular_consumption(ITEM, make_consumption(ste_12=7)))

    def test_rare_item_with_little_consumption_gets_zero(self):
        new_rol, _basis, _ch = compute(make_item(), make_lines(2),
            make_consumption(ste_6=3, ste_12=6), make_con_lines(6, qty=500))
        self.assertEqual(new_rol, 0)

    def test_rare_item_with_regular_consumption_keeps_rol(self):
        itm = make_item(existing_rol=70)
        new_rol, basis, _ch = compute(itm, [], make_consumption(ste_6=4, ste_12=8),
            make_con_lines(8, qty=100))
        self.assertGreater(new_rol, 0)
        self.assertIn("Consumption", basis)
        self.assertNotIn("no ROL", basis)

    def test_consumption_rol_is_lead_time_demand_plus_safety_stock(self):
        # The 365 days are 53 weekly buckets. An entry of 10 in each bucket has no variation,
        # so only the consumption in the lead time counts.
        itm = make_item()
        first_day = add_months(TO_DATE, -12)
        lines = [(add_days(first_day, 7 * k), 10) for k in range(53)]
        self.assertAlmostEqual(get_consumption_rol(itm, lines, TO_DATE), 530 / 365 * 30, 3)
        # The same total in 1 week has variation, so safety stock is added
        spike = [(add_days(TO_DATE, -10), 530)]
        self.assertGreater(get_consumption_rol(itm, spike, TO_DATE), 530 / 365 * 30)

    def test_consumption_is_added_to_the_sales_rol(self):
        # Without the change limits, which would cap both ROLs at the same value
        itm = make_item(existing_rol=500)
        lines = make_lines(60, customers=10)
        with patch("rigpl_erpnext.utils.stock_utils.limit_rol_change",
                side_effect=lambda itm, calc_rol, basis, is_rare: (calc_rol, basis, "same")):
            sales_only = compute(itm, lines, make_consumption())[0]
            both = compute(itm, lines, make_consumption(ste_6=4, ste_12=8),
                make_con_lines(8, qty=100))[0]
        self.assertGreater(both, sales_only)
