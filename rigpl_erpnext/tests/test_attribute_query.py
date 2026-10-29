from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.tests.test_item_attribute_utils import add_item_attribute
from rigpl_erpnext.utils import attribute_query as aq

ATT_1 = "_Test RIGPL AQ Attribute 1"
ATT_2 = "_Test RIGPL AQ Attribute 2"
DOCTYPE = "Item Attribute Value"

WRAPPERS = {
    "attribute_rm_query": ("Is RM",),
    "attribute_bm_query": ("Base Material",),
    "attribute_brand_query": ("Brand",),
    "attribute_quality_query": ("HSS Quality", "Carbide Quality", "Tool Steel Quality"),
    "attribute_tt_query": ("Tool Type",),
    "attribute_spl_query": ("Special Treatment",),
    "attribute_purpose_query": ("Purpose",),
    "attribute_type_query": ("Type Selector",),
    "attribute_mtm_query": ("Material To Machine",),
    "attribute_series_query": ("Series",),
}


class TestAttributeQuery(FrappeTestCase):
    def setUp(self):
        add_item_attribute(ATT_1, 0, ["_Test AQ Zeta", "_Test AQ Alpha", "Some Other AQ"])
        add_item_attribute(ATT_2, 0, ["_Test AQ Beta"])

    def tearDown(self):
        frappe.db.rollback()

    def test_returns_matching_values_of_the_attribute(self):
        rows = aq.search_attribute_values((ATT_1,), "_Test AQ", 0, 20)

        self.assertEqual(
            [tuple(r) for r in rows], [("_Test AQ Alpha", ATT_1), ("_Test AQ Zeta", ATT_1)]
        )

    def test_orders_by_match_position(self):
        rows = aq.search_attribute_values((ATT_1,), "AQ", 0, 20)

        # "Some Other AQ" has the match later in the value than "_Test AQ ..."
        self.assertEqual([r[0] for r in rows], ["_Test AQ Alpha", "_Test AQ Zeta", "Some Other AQ"])

    def test_casts_start_and_page_len(self):
        rows = aq.search_attribute_values((ATT_1,), "_Test AQ", "1", "1")

        self.assertEqual([r[0] for r in rows], ["_Test AQ Zeta"])

    def test_searches_more_than_one_attribute(self):
        rows = aq.search_attribute_values((ATT_1, ATT_2), "_Test AQ", 0, 20)

        self.assertEqual(
            sorted(r[0] for r in rows), ["_Test AQ Alpha", "_Test AQ Beta", "_Test AQ Zeta"]
        )

    def test_txt_that_is_not_a_string_is_not_a_filter(self):
        rows = aq.search_attribute_values((ATT_1,), ["!=", ""], 0, 20)

        self.assertEqual(list(rows), [])

    def test_crafted_searchfield_raises(self):
        with self.assertRaises(frappe.DataError):
            aq.attribute_rm_query(DOCTYPE, "", "name) OR 1=1 -- ", 0, 20, {})

    def test_link_search_searchfield_works(self):
        with patch.object(aq, "QUERY_ATTRIBUTES", {"bm": (ATT_1,)}):
            rows = aq.attribute_bm_query(DOCTYPE, "_Test AQ", "name", 0, 20, {})

        self.assertEqual([r[0] for r in rows], ["_Test AQ Alpha", "_Test AQ Zeta"])

    def test_wrappers_pass_their_attributes(self):
        for name, attributes in WRAPPERS.items():
            with patch.object(aq, "search_attribute_values") as search:
                getattr(aq, name)(DOCTYPE, "x", "name", "0", "20", {})

            search.assert_called_once_with(attributes, "x", 0, 20)
