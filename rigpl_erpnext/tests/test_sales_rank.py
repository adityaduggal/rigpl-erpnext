from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.tests.test_variant_table import insert_item, insert_website_item
from rigpl_erpnext.website_rigpl import sales_rank

TEMPLATE_A = "_Test RIGPL Rank A"
TEMPLATE_B = "_Test RIGPL Rank B"
TODAY = "2026-10-21"


def insert_invoice_row(item_code, amount, posting_date="2026-06-01", docstatus=1):
    invoice = frappe.generate_hash(length=10)
    frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "name": invoice,
            "customer": "_Test RIGPL Customer",
            "posting_date": posting_date,
            "docstatus": docstatus,
        }
    ).db_insert()
    frappe.get_doc(
        {
            "doctype": "Sales Invoice Item",
            "name": frappe.generate_hash(length=10),
            "parent": invoice,
            "parenttype": "Sales Invoice",
            "parentfield": "items",
            "item_code": item_code,
            "base_net_amount": amount,
            "docstatus": docstatus,
        }
    ).db_insert()


class TestRankPure(FrappeTestCase):
    def test_revenue_ranks_first_and_usage_breaks_ties(self):
        ranks = sales_rank.rank_products(["A", "B", "C", "D"], {"A": 10, "B": 50}, {"C": 3, "D": 9})

        # B has the most revenue; C and D have none, so usage decides
        self.assertEqual(ranks, {"B": 4, "A": 3, "D": 2, "C": 1})

    def test_group_revenue_includes_descendants(self):
        groups = [
            {"name": "All", "lft": 1, "rgt": 8},
            {"name": "Carbide", "lft": 2, "rgt": 5},
            {"name": "Drills", "lft": 3, "rgt": 4},
            {"name": "HSS", "lft": 6, "rgt": 7},
        ]
        totals = sales_rank.sum_group_revenue({"Drills": 100, "Carbide": 20, "HSS": 5}, groups)

        self.assertEqual(totals, {"All": 125, "Carbide": 120, "Drills": 100, "HSS": 5})

    def test_weightage_is_revenue_over_a_power_of_ten(self):
        weightages, divisor = sales_rank.scale_weightage(
            {"All": 301017605.7, "HSS": 155883767.8, "Small": 40000, "None": 0, "Returns": -500}
        )

        self.assertEqual(divisor, 1000000)
        self.assertEqual(weightages, {"All": 301, "HSS": 156, "Small": 1, "None": 0, "Returns": 0})
        self.assertEqual(sales_rank.scale_weightage({"A": 1000000, "B": 999}), ({"A": 1000, "B": 1}, 1000))
        self.assertEqual(sales_rank.scale_weightage({"A": 750}), ({"A": 750}, 1))
        self.assertEqual(sales_rank.scale_weightage({}), ({}, 1))


class TestRankData(FrappeTestCase):
    def setUp(self):
        insert_item(TEMPLATE_A)
        insert_item(TEMPLATE_A + " V1", variant_of=TEMPLATE_A)
        insert_item(TEMPLATE_B)
        insert_item(TEMPLATE_B + " V1", variant_of=TEMPLATE_B)
        insert_website_item("_Test RIGPL WEB-RANK-A", TEMPLATE_A)
        insert_website_item("_Test RIGPL WEB-RANK-B", TEMPLATE_B)

    def tearDown(self):
        frappe.db.rollback()

    def test_revenue_of_variants_counts_for_the_template(self):
        insert_invoice_row(TEMPLATE_A + " V1", 300)
        insert_invoice_row(TEMPLATE_A + " V1", -100)  # a credit note reduces the revenue
        insert_invoice_row(TEMPLATE_B + " V1", 150)
        insert_invoice_row(TEMPLATE_B + " V1", 999, docstatus=0)  # a draft does not count
        insert_invoice_row(TEMPLATE_B + " V1", 999, posting_date="2025-01-01")  # too old

        revenue = sales_rank.get_product_revenue("2025-10-21")

        self.assertEqual(revenue[TEMPLATE_A], 200)
        self.assertEqual(revenue[TEMPLATE_B], 150)

    def test_update_writes_ranking_and_a_second_run_writes_nothing(self):
        insert_invoice_row(TEMPLATE_B + " V1", 500)
        insert_invoice_row(TEMPLATE_A + " V1", 100)

        with patch.object(sales_rank, "nowdate", return_value=TODAY):
            sales_rank.update_sales_rank()
            ranking = dict(
                frappe.get_all(
                    "Website Item",
                    filters={"item_code": ("in", [TEMPLATE_A, TEMPLATE_B])},
                    fields=["item_code", "ranking"],
                    as_list=True,
                )
            )
            self.assertGreater(ranking[TEMPLATE_B], ranking[TEMPLATE_A])
            self.assertEqual(sales_rank.update_sales_rank(), (0, 0))

    def test_rank_months_is_the_shortest_rol_period(self):
        with patch.object(frappe.db, "get_single_value", return_value="18, 12,24"):
            self.assertEqual(sales_rank.get_rank_months(), 12)
        with patch.object(frappe.db, "get_single_value", return_value=None):
            self.assertEqual(sales_rank.get_rank_months(), sales_rank.DEFAULT_MONTHS)
