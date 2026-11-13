"""The Sales Order is the only source of rates for the Delivery Note and the Sales Invoice (#223)."""
from unittest.mock import Mock

import frappe

from rigpl_erpnext.rigpl_erpnext.validations import sales_invoice
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw
from rigpl_erpnext.utils.so_rate_utils import check_dn_rates_match_so, copy_so_rates

PRICE_FIELDS = dict(price_list_rate=3027, discount_percentage=54.212, discount_amount=1641, margin_type="",
    margin_rate_or_amount=0, rate_with_margin=0, pricing_rules=None)


def so_row(rate=1386.0, **fields):
    values = dict(PRICE_FIELDS, rate=rate)
    values.update(fields)
    return raw("Sales Order Item", **values)


def doc_with(*rows, **values):
    """Each row is (so_detail, dn_detail, rate). The row has the rule rate and discount that ERPNext gives it."""
    items = [frappe._dict(idx=i + 1, item_code="_Test RIGPL Item", so_detail=so, dn_detail=dn, rate=rate,
        price_list_rate=3027, discount_percentage=62, discount_amount=1876.74, margin_type="",
        margin_rate_or_amount=0, rate_with_margin=0, pricing_rules='["Rule"]')
        for i, (so, dn, rate) in enumerate(rows)]
    doc = Mock(is_return=0, doctype="Sales Invoice")
    doc.name = "_Test RIGPL SI"
    doc.items = items
    doc.get.side_effect = lambda key, default=None: items if key == "items" else values.get(key, default)
    doc.configure_mock(**values)
    return doc


class TestCopySoRates(ReportTestCase):
    def test_rows_get_all_price_fields_of_the_sales_order_in_one_query(self):
        so = so_row()
        doc = doc_with((so, None, 1150.26), (so, None, 1150.26))

        self.assert_queries(1, lambda: copy_so_rates(doc))

        for row in doc.items:
            self.assertEqual((row.rate, row.discount_percentage, row.pricing_rules), (1386.0, 54.212, None))
        message = frappe.parse_json(frappe.message_log[-1])
        self.assertEqual(message["indicator"], "orange")
        self.assertIn("Row# 1, 2", message["message"])
        doc.calculate_taxes_and_totals.assert_called_with()

    def test_rate_typed_by_a_user_is_overwritten(self):
        doc = doc_with((so_row(rate=500, discount_percentage=0, price_list_rate=500, discount_amount=0), None, 450))
        copy_so_rates(doc)
        self.assertEqual(doc.items[0].rate, 500)

    def test_row_with_the_sales_order_rate_gives_no_message(self):
        frappe.message_log.clear()
        doc = doc_with((so_row(), None, 1386.0))
        doc.items[0].update(dict(PRICE_FIELDS, rate=1386.0))
        copy_so_rates(doc)
        self.assertEqual(frappe.message_log, [])
        doc.calculate_taxes_and_totals.assert_not_called()

    def test_rows_without_sales_order_and_returns_are_not_touched(self):
        doc = doc_with((None, None, 100), ("_Test RIGPL No SO Row", None, 100))
        copy_so_rates(doc)
        self.assertEqual([d.rate for d in doc.items], [100, 100])
        doc.calculate_taxes_and_totals.assert_not_called()

        returned = doc_with((so_row(), None, 100), is_return=1)
        copy_so_rates(returned)
        self.assertEqual(returned.items[0].rate, 100)


class TestDnRateMatchesSo(ReportTestCase):
    def dn_row(self, rate):
        return raw("Delivery Note Item", rate=rate)

    def test_drifted_delivery_note_stops_the_invoice(self):
        doc = doc_with((so_row(rate=10), self.dn_row(11), 10))
        with self.assertRaisesRegex(frappe.ValidationError, "SO rate 10.0 / DN rate 11.0"):
            check_dn_rates_match_so(doc)

    def test_same_rate_passes_in_two_queries(self):
        doc = doc_with((so_row(rate=10), self.dn_row(10.004), 10))
        self.assert_queries(2, lambda: check_dn_rates_match_so(doc))

    def test_stop_ignores_the_role(self):
        doc = doc_with((so_row(rate=10), self.dn_row(11), 10))
        frappe.set_user("Administrator")
        self.assertRaises(frappe.ValidationError, check_dn_rates_match_so, doc)

    def test_rows_without_a_delivery_note_are_not_checked(self):
        check_dn_rates_match_so(doc_with((so_row(rate=10), None, 12)))


class TestSalesInvoiceBeforeValidate(ReportTestCase):
    def test_all_rows_from_sales_orders_set_the_ignore_flag_and_the_rates(self):
        so = so_row()
        doc = doc_with((so, None, 1150.26), ignore_pricing_rule=0)
        sales_invoice.before_validate(doc, None)
        self.assertEqual((doc.ignore_pricing_rule, doc.items[0].rate), (1, 1386.0))

    def test_a_row_without_sales_order_keeps_the_pricing_rules_on(self):
        doc = doc_with((so_row(), None, 1150.26), (None, None, 100), ignore_pricing_rule=0)
        sales_invoice.before_validate(doc, None)
        self.assertEqual(doc.ignore_pricing_rule, 0)
        self.assertEqual([d.rate for d in doc.items], [1386.0, 100])
