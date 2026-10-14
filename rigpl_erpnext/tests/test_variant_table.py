import unittest
from unittest.mock import patch

import frappe

from rigpl_erpnext.website_rigpl import catalog, item_page

TEMPLATE = "_Test RIGPL Variant Template"
TEMPLATE_WEB_ITEM = "_Test RIGPL WEB-TEMPLATE"
D1 = "_Test RIGPL d1_mm"  # a numeric Item Attribute that the test makes
L1 = "_Test RIGPL l1_mm"
LABELS = {"Brand": "Brand Name", D1: "Flute Dia (mm)", L1: ""}


def insert_item(name, variant_of=None, disabled=0, attributes=None):
    """Insert raw rows. db_insert skips the RIGPL Item autoname and validate hooks,
    which need real item data that a test site does not have."""
    item = frappe.get_doc(
        {
            "doctype": "Item",
            "name": name,
            "item_code": name,
            "item_name": name,
            "item_group": "All Item Groups",
            "stock_uom": "Nos",
            "has_variants": 0 if variant_of else 1,
            "variant_of": variant_of,
            "disabled": disabled,
        }
    )
    item.db_insert()
    for idx, (attribute, value) in enumerate(attributes or [], start=1):
        frappe.get_doc(
            {
                "doctype": "Item Variant Attribute",
                "name": frappe.generate_hash(length=10),
                "parent": name,
                "parenttype": "Item",
                "parentfield": "attributes",
                "idx": idx,
                "attribute": attribute,
                "attribute_value": value,
                "use_in_description": 0 if attribute == "CETSH Number" else 1,
                "field_name": LABELS.get(attribute, "") if not variant_of else "",
            }
        ).db_insert()


def insert_numeric_attribute(name):
    frappe.get_doc({"doctype": "Item Attribute", "name": name, "attribute_name": name, "numeric_values": 1}).db_insert()


def column(attribute, label, numeric=True):
    return {"attribute": attribute, "label": label, "numeric": numeric}


def insert_website_item(name, item_code, variant_of=None, published=1):
    frappe.get_doc(
        {
            "doctype": "Website Item",
            "name": name,
            "item_code": item_code,
            "web_item_name": item_code,
            "item_group": "All Item Groups",
            "route": frappe.scrub(item_code).replace("_", "-"),
            "has_variants": 0 if variant_of else 1,
            "variant_of": variant_of,
            "published": published,
        }
    ).db_insert()


class TestVariantTable(unittest.TestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_pivot_keeps_variant_order_and_fills_missing_values(self):
        variants = [{"item_code": "B-2", "route": "b-2"}, {"item_code": "A-1", "route": None}]
        values = [
            {"parent": "A-1", "attribute": "d1_mm", "attribute_value": "6"},
            {"parent": "B-2", "attribute": "d1_mm", "attribute_value": "10"},
            {"parent": "B-2", "attribute": "l1_mm", "attribute_value": "75"},
        ]
        rows = catalog.pivot_variant_rows(variants, values, ["d1_mm", "l1_mm"])

        self.assertEqual([r["item_code"] for r in rows], ["B-2", "A-1"])
        self.assertEqual(rows[1]["values"], {"d1_mm": "6", "l1_mm": ""})
        self.assertEqual([r["route"] for r in rows], ["b-2", ""])

    def test_split_columns_moves_constant_attributes_to_common(self):
        rows = [
            {"item_code": "A", "values": {"Brand": "RIGPL", "d1_mm": "6", "Coating": ""}},
            {"item_code": "B", "values": {"Brand": "RIGPL", "d1_mm": "8", "Coating": ""}},
        ]
        attributes = [column("Brand", "Brand Name", False), column("d1_mm", "Flute Dia (mm)"), column("Coating", "Coating", False)]
        common, columns = catalog.split_columns(rows, attributes)

        self.assertEqual(common, [("Brand Name", "RIGPL")])
        self.assertEqual(columns, [attributes[1]])

    def test_split_columns_with_one_variant_has_no_columns(self):
        rows = [{"item_code": "A", "values": {"Brand": "RIGPL", "d1_mm": "6"}}]
        common, columns = catalog.split_columns(rows, [column("Brand", "Brand", False), column("d1_mm", "Flute Dia (mm)")])

        self.assertEqual(common, [("Brand", "RIGPL"), ("Flute Dia (mm)", "6")])
        self.assertEqual(columns, [])

    def test_split_columns_with_no_variants_is_empty(self):
        self.assertEqual(catalog.split_columns([], [column("Brand", "Brand", False)]), ([], []))

    def test_numeric_columns_sort_as_numbers_and_empty_last(self):
        rows = [
            {"item_code": code, "values": {"d1_mm": d1, "l1_mm": l1}}
            for code, d1, l1 in [("A", "10", "50"), ("B", "9", "75"), ("C", "", "50"), ("D", "9", "50"), ("E", "2.5", "50")]
        ]
        ordered = catalog.sort_variant_rows(rows, [column("d1_mm", "d1"), column("l1_mm", "l1")])

        self.assertEqual([r["item_code"] for r in ordered], ["E", "D", "B", "A", "C"])

    def test_text_columns_sort_as_text_and_bad_numbers_after_numbers(self):
        rows = [
            {"item_code": code, "values": {"Coating": coating, "d1_mm": d1}}
            for code, coating, d1 in [("A", "tialn", "x"), ("B", "AlTiN", "3"), ("C", "TiN", "12")]
        ]
        self.assertEqual(
            [r["item_code"] for r in catalog.sort_variant_rows(rows, [column("Coating", "Coating", False)])],
            ["B", "A", "C"],
        )
        self.assertEqual(
            [r["item_code"] for r in catalog.sort_variant_rows(rows, [column("d1_mm", "d1")])],
            ["B", "C", "A"],
        )

    def make_template_with_variants(self, template_published=1):
        insert_numeric_attribute(D1)
        insert_numeric_attribute(L1)
        insert_item(TEMPLATE, attributes=[("Brand", ""), (D1, ""), (L1, ""), ("CETSH Number", "")])
        insert_website_item(TEMPLATE_WEB_ITEM, TEMPLATE, published=template_published)
        variants = {
            "_Test RIGPL V1": ([("Brand", "RIGPL"), (D1, "10"), (L1, "50")], 1),
            "_Test RIGPL V2": ([("Brand", "RIGPL"), (D1, "8"), (L1, "50")], 1),
            "_Test RIGPL V3": ([("Brand", "RIGPL"), (D1, "6")], 0),
        }
        for item_code, (attributes, published) in variants.items():
            insert_item(item_code, TEMPLATE, attributes=attributes)
            insert_website_item("_Test WEB " + item_code, item_code, TEMPLATE, published)

    def test_variant_table_lists_published_variants_in_fixed_queries(self):
        self.make_template_with_variants()

        real_sql = frappe.db.sql
        with patch.object(frappe.db, "sql", side_effect=real_sql) as sql:
            table = catalog.get_variant_table(TEMPLATE_WEB_ITEM)

        self.assertEqual(sql.call_count, 4)
        # d1 8 sorts before d1 10: numeric, not text order
        self.assertEqual([r["item_code"] for r in table["rows"]], ["_Test RIGPL V2", "_Test RIGPL V1"])
        self.assertEqual(table["rows"][1]["route"], "-test-rigpl-v1")
        # labels come from the template Field Name, else the attribute name
        self.assertEqual(table["common"], [("Brand Name", "RIGPL"), (L1, "50")])
        self.assertEqual(table["columns"], [column(D1, "Flute Dia (mm)")])

    def test_unpublished_template_shows_no_variants(self):
        self.make_template_with_variants(template_published=0)
        self.assertEqual(catalog.get_variant_table(TEMPLATE_WEB_ITEM), catalog.empty_table())

    def test_variant_table_rejects_non_string_template(self):
        empty = catalog.empty_table()
        self.assertEqual(catalog.get_variant_table({"name": ["!=", ""]}), empty)
        self.assertEqual(catalog.get_variant_table(""), empty)

    def test_template_website_item_uses_variant_table_page(self):
        template_item = frappe._dict(doctype="Website Item", has_variants=1)
        variant_item = frappe._dict(doctype="Website Item", has_variants=0)

        self.assertEqual(
            item_page.update_website_context(frappe._dict(doc=template_item)),
            {"template": item_page.ITEM_TEMPLATE_PAGE},
        )
        self.assertIsNone(item_page.update_website_context(frappe._dict(doc=variant_item)))
        self.assertIsNone(item_page.update_website_context(frappe._dict(doc=frappe._dict(doctype="Web Page"))))
        self.assertIsNone(item_page.update_website_context(frappe._dict()))

    def test_page_template_exists(self):
        self.assertTrue(frappe.get_jenv().get_template(item_page.ITEM_TEMPLATE_PAGE))
