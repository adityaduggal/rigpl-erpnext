from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.website_rigpl import catalog, item_page

TEMPLATE = "_Test RIGPL Variant Template"
TEMPLATE_WEB_ITEM = "_Test RIGPL WEB-TEMPLATE"
D1 = "_Test RIGPL d1_mm"  # a numeric Item Attribute that the test makes
L1 = "_Test RIGPL l1_mm"
LABELS = {"Brand": "Brand Name", D1: "Flute Dia (mm)", L1: ""}
WAREHOUSE = "_Test RIGPL Web WH"
OTHER_WAREHOUSE = "_Test RIGPL Other WH"
PRICE_LIST = "_Test RIGPL Web Price List"


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


def column(attribute, label, numeric=True, sort_attribute=None):
    return {"attribute": attribute, "label": label, "numeric": numeric, "sort_attribute": sort_attribute or attribute}


def insert_bin(item_code, warehouse, actual_qty, reserved_qty=0):
    frappe.get_doc(
        {
            "doctype": "Bin",
            "name": frappe.generate_hash(length=10),
            "item_code": item_code,
            "warehouse": warehouse,
            "actual_qty": actual_qty,
            "reserved_qty": reserved_qty,
        }
    ).db_insert()


def insert_item_price(item_code, rate, price_list=PRICE_LIST, customer=None):
    frappe.get_doc(
        {
            "doctype": "Item Price",
            "name": frappe.generate_hash(length=10),
            "item_code": item_code,
            "price_list": price_list,
            "price_list_rate": rate,
            "currency": "INR",
            "customer": customer,
        }
    ).db_insert()


def cart_settings(**values):
    settings = dict(
        enabled=1,
        show_price=1,
        show_stock_availability=1,
        show_quantity_in_website=1,
        hide_price_for_guest=0,
        allow_items_not_in_stock=0,
        price_list=PRICE_LIST,
    )
    settings.update(values)
    return frappe._dict(settings)


def insert_website_item(name, item_code, variant_of=None, published=1, warehouse=None):
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
            "website_warehouse": warehouse,
            "stock_uom": "Nos",
        }
    ).db_insert()


class TestVariantTable(FrappeTestCase):
    def setUp(self):
        # get_shopping_cart_settings() reads this request cache first
        frappe.local.shopping_cart_settings = cart_settings()

    def tearDown(self):
        frappe.local.shopping_cart_settings = None
        frappe.set_user("Administrator")
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
        # the variants have no website warehouse, so they use the template's
        insert_website_item(TEMPLATE_WEB_ITEM, TEMPLATE, published=template_published, warehouse=WAREHOUSE)
        variants = {
            "_Test RIGPL V1": ([("Brand", "RIGPL"), (D1, "10"), (L1, "50")], 1),
            "_Test RIGPL V2": ([("Brand", "RIGPL"), (D1, "8"), (L1, "50")], 1),
            "_Test RIGPL V3": ([("Brand", "RIGPL"), (D1, "6")], 0),
        }
        for item_code, (attributes, published) in variants.items():
            insert_item(item_code, TEMPLATE, attributes=attributes)
            insert_website_item("_Test WEB " + item_code, item_code, TEMPLATE, published)

    def count_queries(self):
        real_sql = frappe.db.sql
        with patch.object(frappe.db, "sql", side_effect=real_sql) as sql:
            table = catalog.get_variant_table(TEMPLATE_WEB_ITEM)
        return table, sql.call_count

    def test_variant_table_lists_published_variants_in_fixed_queries(self):
        self.make_template_with_variants()
        frappe.set_user("Guest")
        catalog.get_variant_table(TEMPLATE_WEB_ITEM)  # fills the settings caches

        table, queries = self.count_queries()
        insert_item("_Test RIGPL V4", TEMPLATE, attributes=[("Brand", "RIGPL"), (D1, "12"), (L1, "50")])
        insert_website_item("_Test WEB _Test RIGPL V4", "_Test RIGPL V4", TEMPLATE)
        _, queries_with_one_more = self.count_queries()

        # 4 for the table, 1 Bin, 1 Item Price; one more variant adds no query
        self.assertEqual(queries, 6)
        self.assertEqual(queries_with_one_more, queries)
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

    def test_cap_stock_hides_the_quantity_above_the_cap(self):
        self.assertEqual(catalog.cap_stock(0, 100, "{cap}+", "On request"), "On request")
        self.assertEqual(catalog.cap_stock(-3, 100, "{cap}+", "On request"), "On request")
        self.assertEqual(catalog.cap_stock(37, 100, "{cap}+", "On request"), "37")
        self.assertEqual(catalog.cap_stock(2.5, 100, "{cap}+", "On request"), "2.5")
        self.assertEqual(catalog.cap_stock(100, 100, "{cap}+", "On request"), "100")
        self.assertEqual(catalog.cap_stock(2500, 100, "{cap}+", "On request"), "100+")
        self.assertEqual(catalog.cap_stock(2500, 50, "More than {cap}", "-"), "More than 50")
        self.assertEqual(catalog.cap_stock(37, 100, "{cap}+", "On request", show_qty=False), "In stock")

    def test_text_size_sorts_by_its_numeric_twin(self):
        rows = [
            frappe._dict(attribute="d1_mm", numeric_values=1, source="UOM", update_from="d1"),
            frappe._dict(attribute="d1_inch", numeric_values=0, source="UOM", update_from="d1"),
            frappe._dict(attribute="Coating", numeric_values=0, source=None, update_from=None),
            frappe._dict(attribute="w1_inch", numeric_values=0, source="UOM", update_from="w1"),
        ]

        self.assertEqual(
            catalog.pick_sort_attribute(rows[1], rows), {"numeric": True, "sort_attribute": "d1_mm"}
        )
        self.assertEqual(
            catalog.pick_sort_attribute(rows[0], rows), {"numeric": True, "sort_attribute": "d1_mm"}
        )
        # no twin: sorts by its own value, as text
        self.assertEqual(
            catalog.pick_sort_attribute(rows[2], rows), {"numeric": False, "sort_attribute": "Coating"}
        )
        self.assertEqual(
            catalog.pick_sort_attribute(rows[3], rows), {"numeric": False, "sort_attribute": "w1_inch"}
        )

    def test_rows_sort_by_the_twin_value_not_the_text(self):
        rows = [
            {"item_code": code, "values": {"d1_inch": inch, "d1_mm": mm}}
            for code, inch, mm in [("A", "1/4", "6.35"), ("B", "1/8", "3.175"), ("C", "3/16", "4.763"), ("D", "3/8", "")]
        ]
        columns = [column("d1_inch", "Height (inch)", sort_attribute="d1_mm")]

        # an empty twin value sorts last
        self.assertEqual([r["item_code"] for r in catalog.sort_variant_rows(rows, columns)], ["B", "C", "A", "D"])

    def test_stock_sort_value_is_never_above_the_cap(self):
        self.assertEqual(catalog.stock_sort_value(0, 100), 0)
        self.assertEqual(catalog.stock_sort_value(-3, 100), 0)
        self.assertEqual(catalog.stock_sort_value(37, 100), 37)
        self.assertEqual(catalog.stock_sort_value(2500, 100), 100)
        self.assertEqual(catalog.stock_sort_value(2500, 100, show_qty=False), 1)

    def test_add_shop_info_returns_new_rows(self):
        rows = [{"item_code": "A", "values": {}}, {"item_code": "B", "values": {}}]
        shop_rows = {"A": {"stock": "5", "price": "₹ 10.00", "price_value": 10.0, "can_add": True}}
        result = catalog.add_shop_info(rows, shop_rows)

        self.assertEqual(result[0]["shop"], shop_rows["A"])
        self.assertEqual(result[1]["shop"]["can_add"], False)
        self.assertNotIn("shop", rows[0])

    def make_shop_data(self):
        self.make_template_with_variants()
        insert_bin("_Test RIGPL V1", WAREHOUSE, 2500)
        insert_bin("_Test RIGPL V1", OTHER_WAREHOUSE, 7)  # not the website warehouse
        insert_bin("_Test RIGPL V2", WAREHOUSE, 40, reserved_qty=43)
        insert_bin("_Test RIGPL V2", OTHER_WAREHOUSE, 900)
        insert_item_price("_Test RIGPL V1", 627)
        insert_item_price(TEMPLATE, 500)  # V2 has no price of its own
        insert_item_price("_Test RIGPL V2", 1, customer="_Test RIGPL Customer")

    def shop_by_item(self, table):
        return {row["item_code"]: row["shop"] for row in table["rows"]}

    def test_shop_columns_show_capped_stock_and_list_price(self):
        self.make_shop_data()
        frappe.set_user("Guest")
        table = catalog.get_variant_table(TEMPLATE_WEB_ITEM)
        shop = self.shop_by_item(table)

        self.assertEqual(
            table["shop"], {"show_stock": True, "show_qty": True, "show_price": True, "show_cart": True}
        )
        # only the website warehouse counts, and the reserved qty is free stock no more
        self.assertEqual(shop["_Test RIGPL V1"]["stock"], "100+")
        self.assertEqual(shop["_Test RIGPL V2"]["stock"], "On request")
        # the sort value is capped as well
        self.assertEqual(shop["_Test RIGPL V1"]["stock_value"], 100)
        self.assertEqual(shop["_Test RIGPL V2"]["stock_value"], 0)
        self.assertEqual(shop["_Test RIGPL V1"]["uom"], "Nos")
        self.assertEqual(shop["_Test RIGPL V1"]["price_value"], 627)
        # a variant with no price uses the template price; a customer price is skipped
        self.assertEqual(shop["_Test RIGPL V2"]["price_value"], 500)
        self.assertTrue(shop["_Test RIGPL V1"]["can_add"])
        self.assertFalse(shop["_Test RIGPL V2"]["can_add"])  # no stock

    def test_items_not_in_stock_can_be_added_when_allowed(self):
        self.make_shop_data()
        frappe.local.shopping_cart_settings = cart_settings(allow_items_not_in_stock=1)
        frappe.set_user("Guest")
        shop = self.shop_by_item(catalog.get_variant_table(TEMPLATE_WEB_ITEM))

        self.assertTrue(shop["_Test RIGPL V2"]["can_add"])

    def test_price_hidden_for_guest_also_blocks_add_to_cart(self):
        self.make_shop_data()
        frappe.local.shopping_cart_settings = cart_settings(hide_price_for_guest=1)
        frappe.set_user("Guest")
        table = catalog.get_variant_table(TEMPLATE_WEB_ITEM)

        self.assertFalse(table["shop"]["show_price"])
        self.assertEqual({s["price"] for s in self.shop_by_item(table).values()}, {""})
        self.assertFalse(any(s["can_add"] for s in self.shop_by_item(table).values()))

    def test_disabled_cart_shows_no_shop_columns(self):
        self.make_shop_data()
        frappe.local.shopping_cart_settings = cart_settings(enabled=0)
        table = catalog.get_variant_table(TEMPLATE_WEB_ITEM)

        self.assertEqual(table["shop"], catalog.no_shop())

    def test_page_never_contains_the_quantity_above_the_cap(self):
        self.make_shop_data()
        frappe.set_user("Guest")
        html = frappe.render_template(
            "rigpl_erpnext/website_rigpl/web_template/rigpl_variant_table/rigpl_variant_table.html",
            {"website_item": TEMPLATE_WEB_ITEM},
        )

        self.assertIn("100+", html)
        self.assertNotIn("2500", html)
        self.assertIn('data-rigpl-add="_Test RIGPL V1"', html)
        self.assertNotIn('data-rigpl-add="_Test RIGPL V2"', html)

    def render_table(self):
        return frappe.render_template(
            "rigpl_erpnext/website_rigpl/web_template/rigpl_variant_table/rigpl_variant_table.html",
            {"website_item": TEMPLATE_WEB_ITEM},
        )

    def test_price_stock_and_cart_share_one_column(self):
        self.make_shop_data()
        frappe.set_user("Guest")
        html = self.render_table()

        self.assertEqual(html.count('<th scope="col" data-type="number" class="rigpl-variant-buy">'), 1)
        self.assertEqual(html.count('<td class="rigpl-variant-buy"'), 2)
        self.assertIn("/ Nos</span>", html)
        self.assertIn('<span class="rigpl-buy-stock-label">In stock:</span>', html)
        self.assertIn("Stock: On request", html)
        self.assertIn('data-sort-stock="100"', html)
        self.assertIn('<a class="rigpl-enquire" href="/contact">Enquire</a>', html)
        self.assertIn(':desc:stock">Stock ↓</option>', html)

    def test_price_column_without_prices_sorts_by_stock(self):
        self.make_shop_data()
        frappe.local.shopping_cart_settings = cart_settings(hide_price_for_guest=1)
        frappe.set_user("Guest")
        html = self.render_table()

        self.assertIn('<button type="button">Stock</button>', html)
        self.assertNotIn("Price ↑", html)
        self.assertNotIn("rigpl-buy-price", html)
        self.assertIn('data-sort="100"', html)

    def test_table_stock_matches_erpnext_web_stock(self):
        from erpnext.utilities.product import get_web_item_qty_in_stock

        self.make_shop_data()
        # V1 sells in boxes of 10, so ERPNext counts its stock in boxes
        frappe.db.set_value("Item", "_Test RIGPL V1", "sales_uom", "_Test RIGPL Box", update_modified=False)
        frappe.get_doc(
            {
                "doctype": "UOM Conversion Detail",
                "name": frappe.generate_hash(length=10),
                "parent": "_Test RIGPL V1",
                "parenttype": "Item",
                "parentfield": "uoms",
                "uom": "_Test RIGPL Box",
                "conversion_factor": 10,
            }
        ).db_insert()
        table_stock = catalog.get_stock_qty({"_Test RIGPL V1": WAREHOUSE, "_Test RIGPL V2": WAREHOUSE})

        for item_code in ("_Test RIGPL V1", "_Test RIGPL V2"):
            erpnext_qty = get_web_item_qty_in_stock(item_code, "website_warehouse").stock_qty[0][0]
            self.assertEqual(table_stock[item_code], erpnext_qty)
        self.assertEqual(table_stock["_Test RIGPL V1"], 250)
        shop = self.shop_by_item(catalog.get_variant_table(TEMPLATE_WEB_ITEM))
        self.assertEqual(shop["_Test RIGPL V1"]["stock_uom"], "_Test RIGPL Box")
        self.assertEqual(shop["_Test RIGPL V1"]["uom"], "Nos")  # the price stays per stock UOM

    def test_cap_product_info_hides_the_quantity_above_the_cap(self):
        product_info = {"stock_qty": [[2500]], "in_stock": 1, "uom": "Nos"}
        capped = catalog.cap_product_info(product_info)

        self.assertEqual(capped, {"stock_qty": [["100+"]], "in_stock": 1, "uom": "Nos"})
        self.assertEqual(product_info["stock_qty"], [[2500]])  # a copy, not changed in place
        self.assertEqual(catalog.cap_product_info({"stock_qty": [[37]]})["stock_qty"], [["37"]])
        self.assertEqual(catalog.cap_product_info({"stock_qty": ""}), {"stock_qty": ""})
        self.assertEqual(catalog.cap_product_info({}), {})

    def test_variant_page_shows_the_capped_stock(self):
        context = frappe._dict(
            doc=frappe._dict(doctype="Website Item", has_variants=0),
            shopping_cart=frappe._dict(product_info={"stock_qty": [[2500]]}, cart_settings=frappe._dict(enabled=1)),
        )
        values = item_page.update_website_context(context)

        self.assertEqual(values["shopping_cart"].product_info["stock_qty"], [["100+"]])
        self.assertEqual(values["shopping_cart"].cart_settings, context.shopping_cart.cart_settings)
        self.assertEqual(context.shopping_cart.product_info["stock_qty"], [[2500]])

    def test_guest_api_returns_the_capped_stock(self):
        from rigpl_erpnext.website_rigpl import product_info

        erpnext_path = "erpnext.e_commerce.shopping_cart.product_info.get_product_info_for_website"
        self.assertEqual(
            frappe.get_hooks("override_whitelisted_methods").get(erpnext_path),
            ["rigpl_erpnext.website_rigpl.product_info.get_product_info_for_website"],
        )
        erpnext_result = frappe._dict(product_info={"stock_qty": [[2500]], "in_stock": 1}, cart_settings={})
        with patch.object(product_info, "erpnext_get_product_info_for_website", return_value=erpnext_result):
            result = product_info.get_product_info_for_website("_Test RIGPL V1")

        self.assertEqual(result.product_info["stock_qty"], [["100+"]])
        self.assertNotIn("2500", frappe.as_json(result))

    def test_place_order_message_shows_the_capped_stock(self):
        from rigpl_erpnext.website_rigpl import cart

        self.assertEqual(
            frappe.get_hooks("override_whitelisted_methods").get("erpnext.e_commerce.shopping_cart.cart.place_order"),
            ["rigpl_erpnext.website_rigpl.cart.place_order"],
        )
        self.make_shop_data()
        frappe.db.set_value("Item", "_Test RIGPL V1", "is_stock_item", 1, update_modified=False)
        quotation = frappe._dict(items=[frappe._dict(item_code="_Test RIGPL V1", qty=3000)])

        with self.assertRaises(frappe.ValidationError) as raised:
            cart.check_cart_stock(quotation)
        self.assertIn("100+", str(raised.exception))
        self.assertNotIn("2500", str(raised.exception))
        frappe.clear_messages()

        # an order within the stock passes to ERPNext's place order
        cart.check_cart_stock(frappe._dict(items=[frappe._dict(item_code="_Test RIGPL V1", qty=5)]))
        frappe.local.shopping_cart_settings = cart_settings(allow_items_not_in_stock=1)
        cart.check_cart_stock(quotation)

    def variant_page_context(self):
        return frappe._dict(
            doc=frappe._dict(doctype="Website Item", has_variants=0, variant_of=TEMPLATE),
            parents=[{"name": "Home", "route": "/"}, {"name": "HSS Tools", "route": "hss"}],
        )

    def test_variant_breadcrumb_ends_with_its_template(self):
        self.make_template_with_variants()
        context = self.variant_page_context()
        values = item_page.update_website_context(context)

        self.assertEqual(
            values["parents"],
            [
                {"name": "Home", "route": "/"},
                {"name": "HSS Tools", "route": "hss"},
                {"name": TEMPLATE, "route": "-test-rigpl-variant-template"},
            ],
        )
        self.assertEqual(len(context.parents), 2)  # ERPNext's list is not changed

    def test_variant_of_an_unpublished_template_keeps_erpnext_breadcrumb(self):
        self.make_template_with_variants(template_published=0)
        self.assertIsNone(item_page.update_website_context(self.variant_page_context()))
