from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.patches.v13 import website_item_group_listing
from rigpl_erpnext.website_rigpl import product_listing


def group(name):
    return frappe._dict(name=name, route=frappe.scrub(name))


class TestProductListing(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_sub_categories_sort_by_weightage_then_name(self):
        groups = [group("Drills"), group("End Mills"), group("Reamers"), group("Taps")]
        ordered = product_listing.sort_sub_categories(groups, {"End Mills": 301, "Reamers": 12, "Taps": 12})

        self.assertEqual([g.name for g in ordered], ["End Mills", "Reamers", "Taps", "Drills"])

    def test_api_keeps_erpnext_result_and_orders_sub_categories(self):
        erpnext_result = {
            "items": ["the products"],
            "sub_categories": [group("All Item Groups"), group("_Test Item Group")],
        }
        guest_api = "erpnext.e_commerce.api.get_product_filter_data"

        weightages = [["All Item Groups", 0], ["_Test Item Group", 50]]
        with patch.object(product_listing, "erpnext_get_product_filter_data", return_value=erpnext_result), patch.object(
            frappe, "get_all", return_value=weightages
        ):
            result = product_listing.get_product_filter_data({"item_group": "All Item Groups"})

        self.assertEqual(result["items"], ["the products"])
        self.assertEqual([g.name for g in result["sub_categories"]], ["_Test Item Group", "All Item Groups"])
        self.assertEqual(
            frappe.get_hooks("override_whitelisted_methods").get(guest_api),
            ["rigpl_erpnext.website_rigpl.product_listing.get_product_filter_data"],
        )

    def test_api_passes_an_error_result_through(self):
        with patch.object(product_listing, "erpnext_get_product_filter_data", return_value={"exc": "error"}):
            self.assertEqual(product_listing.get_product_filter_data({}), {"exc": "error"})

    def test_patch_shows_templates_only_and_runs_twice(self):
        frappe.db.set_single_value("E Commerce Settings", "hide_variants", 0)
        frappe.db.set_single_value("E Commerce Settings", "enable_attribute_filters", 1)

        website_item_group_listing.execute()
        website_item_group_listing.execute()

        self.assertEqual(frappe.db.get_single_value("E Commerce Settings", "hide_variants"), 1)
        self.assertEqual(frappe.db.get_single_value("E Commerce Settings", "enable_attribute_filters"), 0)
        self.assertFalse(
            frappe.db.exists("Item Group", {"show_in_website": 1, "is_group": 1, "include_descendants": 0})
        )
