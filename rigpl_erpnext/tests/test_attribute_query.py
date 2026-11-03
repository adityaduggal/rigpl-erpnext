from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.tests.test_item_attribute_utils import add_item_attribute
from rigpl_erpnext.tests.test_variant_table import insert_item
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


DLG_TEMPLATE = "_Test RIGPL Dialog Template"
DLG_BM = "_Test RIGPL Dialog BM"
DLG_D1_MM = "_Test RIGPL Dialog d1_mm"
DLG_D1_INCH = "_Test RIGPL Dialog d1_inch"
DLG_A1 = "_Test RIGPL Dialog a1_deg"
DLG_LINK = "_Test RIGPL Dialog d1"


class TestVariantDialogData(FrappeTestCase):
    def setUp(self):
        add_item_attribute(DLG_BM, 0, ["HSS", "Carbide"])
        add_item_attribute(DLG_D1_MM, 1)
        add_item_attribute(DLG_D1_INCH, 0, [f"{i}/64" for i in range(1, 30)])
        add_item_attribute(DLG_A1, 1)
        for name, link, uom in ((DLG_D1_MM, DLG_LINK, "mm"), (DLG_D1_INCH, DLG_LINK, "Inch"),
                (DLG_A1, "_Test RIGPL Dialog a1", "Degree")):
            frappe.db.set_value("Item Attribute", name,
                {"hidden": 1, "update_from": link, "source": "UOM", "relation": uom})
        insert_item(DLG_TEMPLATE)
        rows = [(DLG_BM, 1), (DLG_D1_MM, 0), (DLG_D1_INCH, 1), (DLG_A1, 1)]
        for idx, (attribute, shown) in enumerate(rows, start=1):
            frappe.get_doc(
                doctype="Item Variant Attribute",
                name=frappe.generate_hash(length=10),
                parent=DLG_TEMPLATE,
                parenttype="Item",
                parentfield="attributes",
                idx=idx,
                attribute=attribute,
                use_in_description=shown,
            ).db_insert()

    def tearDown(self):
        frappe.db.rollback()
        frappe.set_user("Administrator")

    def test_values_are_all_in_idx_order(self):
        data = aq.get_variant_dialog_data(DLG_TEMPLATE)
        self.assertEqual(data["values"][DLG_BM], ["HSS", "Carbide"])
        # frappe.client.get_list returned only 20 values
        self.assertEqual(len(data["values"][DLG_D1_INCH]), 29)
        self.assertNotIn(DLG_D1_MM, data["values"])

    def test_default_uom_is_the_shown_one_or_the_only_one(self):
        links = aq.get_variant_dialog_data(DLG_TEMPLATE)["links"]
        self.assertEqual(links[DLG_LINK]["uoms"], {DLG_D1_MM: "mm", DLG_D1_INCH: "Inch"})
        self.assertEqual(links[DLG_LINK]["default_uom"], "Inch")
        self.assertEqual(links["_Test RIGPL Dialog a1"]["default_uom"], "Degree")

    def test_no_default_uom_if_two_are_shown(self):
        links = aq.get_dialog_links([
            frappe._dict(attribute="a", hidden=1, update_from="d1", source="UOM", relation="mm", use_in_description=1),
            frappe._dict(attribute="b", hidden=1, update_from="d1", source="UOM", relation="Inch", use_in_description=1),
        ])
        self.assertIsNone(links["d1"]["default_uom"])

    def test_not_a_template_or_bad_input_throws(self):
        insert_item("_Test RIGPL Dialog Variant", variant_of=DLG_TEMPLATE)
        self.assertRaises(frappe.ValidationError, aq.get_variant_dialog_data, "_Test RIGPL Dialog Variant")
        self.assertRaises(frappe.ValidationError, aq.get_variant_dialog_data, ["!=", ""])

    def test_needs_read_permission_on_the_template(self):
        frappe.set_user("Guest")
        self.assertRaises(frappe.PermissionError, aq.get_variant_dialog_data, DLG_TEMPLATE)

    def test_uom_factor_map(self):
        self.assertEqual(aq.get_uom_factor_map(["mm"]), {})
        factors = aq.get_uom_factor_map(["Inch", "mm"])
        for from_uom, to_uoms in factors.items():
            self.assertIn(from_uom, ("Inch", "mm"))
            self.assertTrue(set(to_uoms) <= {"Inch", "mm"})
