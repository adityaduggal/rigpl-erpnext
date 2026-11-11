from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.tests.test_variant_table import insert_item, insert_website_item
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.website_rigpl.item_sync import (
    build_search_rows,
    build_web_specs,
    get_current_specs,
    make_missing_web_items,
    on_item_update,
    plan_web_item_changes,
    set_web_long_description,
    get_search_rows,
    strip_quotes,
    sync_web_items,
    sync_web_search,
    sync_web_specs,
)

IMAGE = "/files/_test_rigpl_330.jpg"
TEMPLATE = "_Test RIGPL Sync Template"
VARIANT = "_Test RIGPL Sync Variant"


def row(image=IMAGE, website_image=IMAGE, thumbnail=IMAGE, published=1, disabled=0, pl_item=1):
    return {
        "name": "W1",
        "image": image,
        "website_image": website_image,
        "thumbnail": thumbnail,
        "published": published,
        "disabled": disabled,
        "pl_item": pl_item,
    }


class TestPlanWebItemChanges(FrappeTestCase):
    def test_row_in_sync_has_no_changes(self):
        self.assertEqual(plan_web_item_changes([row()]), {})

    def test_empty_and_none_are_the_same(self):
        self.assertEqual(plan_web_item_changes([row(image="", website_image=None, thumbnail="")]), {})

    def test_image_comes_from_item(self):
        changes = plan_web_item_changes([row(website_image=None, thumbnail="/files/old.jpg")])
        self.assertEqual(changes, {"W1": {"website_image": IMAGE, "thumbnail": IMAGE}})

    def test_only_wrong_fields_change(self):
        self.assertEqual(plan_web_item_changes([row(thumbnail=None)]), {"W1": {"thumbnail": IMAGE}})

    def test_pl_item_no_unpublishes(self):
        self.assertEqual(plan_web_item_changes([row(pl_item=0)]), {"W1": {"published": 0}})

    def test_disabled_unpublishes(self):
        self.assertEqual(plan_web_item_changes([row(disabled=1)]), {"W1": {"published": 0}})

    def test_enabled_price_list_item_publishes(self):
        self.assertEqual(plan_web_item_changes([row(published=0)]), {"W1": {"published": 1}})

    def test_website_warehouse_comes_from_item_default(self):
        changed = dict(row(), default_warehouse="Stores - X", website_warehouse=None)
        self.assertEqual(plan_web_item_changes([changed]), {"W1": {"website_warehouse": "Stores - X"}})

    def test_item_without_default_warehouse_keeps_website_warehouse(self):
        kept = dict(row(), default_warehouse=None, website_warehouse="Stores - X")
        self.assertEqual(plan_web_item_changes([kept]), {})


class TestStripQuotes(FrappeTestCase):
    def test_strip_quotes(self):
        self.assertEqual(strip_quotes('"Solid Carbide"'), "Solid Carbide")
        self.assertEqual(strip_quotes('""'), "")
        self.assertEqual(strip_quotes("Solid Carbide"), "Solid Carbide")
        self.assertEqual(strip_quotes('"'), '"')


class TestSyncWebItems(FrappeTestCase):
    def setUp(self):
        insert_item(TEMPLATE)
        insert_item(VARIANT, variant_of=TEMPLATE)
        for name in (TEMPLATE, VARIANT):
            frappe.db.set_value("Item", name, {"image": IMAGE, "pl_item": 1}, update_modified=False)
        insert_website_item("_Test RIGPL WEB-SYNC-T", TEMPLATE)
        insert_website_item("_Test RIGPL WEB-SYNC-V", VARIANT, variant_of=TEMPLATE)

    def tearDown(self):
        frappe.db.rollback()
        delete_test_search_rows()

    def web_item(self, item_code):
        return frappe.db.get_value(
            "Website Item",
            {"item_code": item_code},
            ["website_image", "thumbnail", "published", "web_long_description"],
            as_dict=True,
        )

    def test_sync_copies_image_and_second_run_writes_nothing(self):
        self.assertEqual(sync_web_items([TEMPLATE, VARIANT]), 2)
        self.assertEqual(self.web_item(TEMPLATE).website_image, IMAGE)
        self.assertEqual(self.web_item(VARIANT).thumbnail, IMAGE)
        self.assertEqual(sync_web_items([TEMPLATE, VARIANT]), 0)

    def test_empty_item_list_changes_nothing(self):
        self.assertEqual(sync_web_items([]), 0)
        self.assertIsNone(self.web_item(TEMPLATE).website_image)

    def test_hook_follows_item_image_and_pl_item(self):
        sync_web_items([VARIANT])
        frappe.db.set_value("Item", VARIANT, {"image": "/files/new.jpg", "pl_item": 0}, update_modified=False)
        on_item_update(item_doc(VARIANT, variant_of=TEMPLATE))

        web_item = self.web_item(VARIANT)
        self.assertEqual(web_item.website_image, "/files/new.jpg")
        self.assertEqual(web_item.published, 0)
        self.assertTrue(frappe.db.exists("Website Item", {"item_code": VARIANT}))

    def test_hook_writes_generated_long_description_for_variant_only(self):
        on_item_update(item_doc(VARIANT, variant_of=TEMPLATE, long_desc="Dia 10 mm"))
        on_item_update(item_doc(TEMPLATE, long_desc=TEMPLATE))

        self.assertEqual(self.web_item(VARIANT).web_long_description, "Dia 10 mm")
        self.assertIsNone(self.web_item(TEMPLATE).web_long_description)

    def test_missing_web_item_is_made_only_for_an_enabled_price_list_item(self):
        insert_item("_Test RIGPL Sync New", variant_of=TEMPLATE)
        insert_item("_Test RIGPL Sync Not PL", variant_of=TEMPLATE)
        insert_item("_Test RIGPL Sync Disabled", variant_of=TEMPLATE, disabled=1)
        for name in ("_Test RIGPL Sync New", "_Test RIGPL Sync Disabled"):
            frappe.db.set_value("Item", name, "pl_item", 1, update_modified=False)
        codes = ["_Test RIGPL Sync New", "_Test RIGPL Sync Not PL", "_Test RIGPL Sync Disabled", VARIANT]

        with patch("erpnext.e_commerce.doctype.website_item.website_item.make_website_item") as make:
            made = make_missing_web_items(codes)

        # VARIANT has a Website Item already
        self.assertEqual(made, 1)
        self.assertEqual([call.args[0].name for call in make.call_args_list], ["_Test RIGPL Sync New"])
        self.assertEqual(make_missing_web_items([]), 0)

    def test_missing_web_item_is_made_without_a_file(self):
        """#218: make_thumbnail made a File with no file_name, and the Item save failed."""
        # Website Item validate refuses a route that starts with "-", so no leading "_" here.
        code = "Test RIGPL Sync No File"
        frappe.db.set_value("Website Item", {"item_code": TEMPLATE}, "route", "test-rigpl-sync-template")
        # the setUp Website Item is db_insert, so the template Item is not marked published yet
        frappe.db.set_value("Item", TEMPLATE, "published_in_website", 1, update_modified=False)
        insert_item(code, variant_of=TEMPLATE)
        frappe.db.set_value("Item", code, {"image": IMAGE, "pl_item": 1}, update_modified=False)
        files = frappe.db.count("File")

        on_item_update(item_doc(code, variant_of=TEMPLATE))

        web_item = self.web_item(code)
        self.assertEqual((web_item.website_image, web_item.thumbnail, web_item.published), (IMAGE, IMAGE, 1))
        self.assertEqual(frappe.db.count("File"), files)

    def test_long_description_writes_only_a_difference(self):
        self.assertTrue(set_web_long_description(VARIANT, "Dia 10 mm"))
        self.assertFalse(set_web_long_description(VARIANT, "Dia 10 mm"))
        self.assertFalse(set_web_long_description("_Test RIGPL No Web Item", "Dia 10 mm"))


SPEC_TEMPLATE = "_Test RIGPL Spec Template"
SPEC_VARIANT = "_Test RIGPL Spec Variant"
SPEC_WEB_ITEM = "_Test RIGPL WEB-SPEC-V"
SPEC_BM = "_Test RIGPL Spec BM"
SPEC_D1 = "_Test RIGPL Spec d1_mm"
SPEC_HIDDEN = "_Test RIGPL Spec Hidden"


class TestSyncWebSpecs(FrappeTestCase):
    def setUp(self):
        insert_attribute(SPEC_BM, values={"Carbide": '"Solid Carbide"', "None": '""'})
        insert_attribute(SPEC_D1, numeric=1)
        insert_attribute(SPEC_HIDDEN, values={"X": '"X"'})
        insert_item(SPEC_TEMPLATE)
        insert_item(SPEC_VARIANT, variant_of=SPEC_TEMPLATE)
        frappe.db.set_value("Item", SPEC_VARIANT, "pl_item", 1, update_modified=False)
        insert_attribute_rows(SPEC_TEMPLATE, [(SPEC_D1, None, "Dia (mm)", 1), (SPEC_BM, None, "Material", 1),
            (SPEC_HIDDEN, None, "Hidden", 0)])
        insert_attribute_rows(SPEC_VARIANT, [(SPEC_D1, "4.5", "", 0), (SPEC_BM, "Carbide", "", 0),
            (SPEC_HIDDEN, "X", "", 0)])
        insert_website_item(SPEC_WEB_ITEM, SPEC_VARIANT, variant_of=SPEC_TEMPLATE)

    def tearDown(self):
        frappe.db.rollback()
        delete_test_search_rows()

    def test_specs_follow_template_order_and_use_in_description(self):
        self.assertEqual(
            build_web_specs([SPEC_VARIANT, SPEC_TEMPLATE]),
            {SPEC_VARIANT: [("Dia (mm)", "4.5"), ("Material", "Solid Carbide")]},
        )

    def test_empty_long_description_stays_empty(self):
        frappe.db.set_value("Item Variant Attribute", {"parent": SPEC_VARIANT, "attribute": SPEC_BM},
            "attribute_value", "None")
        self.assertEqual(build_web_specs([SPEC_VARIANT])[SPEC_VARIANT][1], ("Material", ""))

    def test_only_enabled_price_list_variants(self):
        frappe.db.set_value("Item", SPEC_VARIANT, "pl_item", 0, update_modified=False)
        self.assertEqual(build_web_specs([SPEC_VARIANT]), {})
        self.assertEqual(build_web_specs([]), {})

    def test_sync_writes_rows_once(self):
        with assert_max_queries(10, test_case=self):
            self.assertEqual(sync_web_specs([SPEC_VARIANT]), 1)
        self.assertEqual(
            get_current_specs([SPEC_WEB_ITEM]),
            {SPEC_WEB_ITEM: [("Dia (mm)", "4.5"), ("Material", "Solid Carbide")]},
        )
        self.assertEqual(sync_web_specs([SPEC_VARIANT]), 0)

    def test_sync_replaces_old_rows(self):
        sync_web_specs([SPEC_VARIANT])
        frappe.db.set_value("Item Variant Attribute", {"parent": SPEC_TEMPLATE, "attribute": SPEC_BM},
            "field_name", "Coating")
        self.assertEqual(sync_web_specs([SPEC_VARIANT]), 1)
        self.assertEqual(get_current_specs([SPEC_WEB_ITEM])[SPEC_WEB_ITEM][1], ("Coating", "Solid Carbide"))

    def test_hook_writes_specs_for_variant(self):
        on_item_update(item_doc(SPEC_VARIANT, variant_of=SPEC_TEMPLATE))
        self.assertEqual(len(get_current_specs([SPEC_WEB_ITEM])[SPEC_WEB_ITEM]), 2)


SEARCH_ITEM = "_Test RIGPL Search HR4XSQ00T01"
SEARCH_WEB_ITEM = "_Test RIGPL WEB-SEARCH"


class TestSyncWebSearch(FrappeTestCase):
    def setUp(self):
        insert_item(SEARCH_ITEM)
        insert_website_item(SEARCH_WEB_ITEM, SEARCH_ITEM)
        frappe.db.set_value("Website Item", SEARCH_WEB_ITEM, "web_item_name", "Square <b>Tool</b> Bit")

    def tearDown(self):
        frappe.db.rollback()
        delete_test_search_rows()

    def test_row_has_item_code_and_name(self):
        row = build_search_rows([{"name": "W1", "web_item_name": "Square Tool Bit", "item_code": "HR1",
            "published": 1, "route": "hss/hr1"}])["W1"]
        self.assertEqual(row, {
            "content": "Website Item Name : Square Tool Bit ||| Item Code : HR1",
            "published": 1,
            "title": "Square Tool Bit",
            "route": "hss/hr1",
        })

    def test_sync_writes_once_and_follows_publish(self):
        with assert_max_queries(6, test_case=self):
            self.assertEqual(sync_web_search([SEARCH_ITEM]), 1)
        row = get_search_rows([SEARCH_WEB_ITEM])[SEARCH_WEB_ITEM]
        self.assertIn(SEARCH_ITEM, row["content"])
        self.assertIn("Square Tool Bit", row["content"])
        self.assertEqual(row["published"], 1)
        self.assertEqual(sync_web_search([SEARCH_ITEM]), 0)

        frappe.db.set_value("Website Item", SEARCH_WEB_ITEM, "published", 0)
        self.assertEqual(sync_web_search([SEARCH_ITEM]), 1)
        self.assertEqual(get_search_rows([SEARCH_WEB_ITEM])[SEARCH_WEB_ITEM]["published"], 0)
        self.assertEqual(sync_web_search([]), 0)


def delete_test_search_rows():
    """__global_search is MyISAM, so a rollback does not remove its rows."""
    search = frappe.qb.Table("__global_search")
    frappe.qb.from_(search).delete().where(
        (search.doctype == "Website Item") & search.name.like("\\_Test RIGPL%")
    ).run()


def insert_attribute(name, numeric=0, values=None):
    frappe.get_doc(
        {"doctype": "Item Attribute", "name": name, "attribute_name": name, "numeric_values": numeric}
    ).db_insert()
    for idx, (value, long_description) in enumerate((values or {}).items(), start=1):
        frappe.get_doc(
            {
                "doctype": "Item Attribute Value",
                "name": frappe.generate_hash(length=10),
                "parent": name,
                "parenttype": "Item Attribute",
                "parentfield": "item_attribute_values",
                "idx": idx,
                "attribute_value": value,
                "abbr": value,
                "long_description": long_description,
            }
        ).db_insert()


def insert_attribute_rows(item_code, rows):
    """rows: [(attribute, value, field_name, use_in_description)]"""
    for idx, (attribute, value, field_name, use_in_description) in enumerate(rows, start=1):
        frappe.get_doc(
            {
                "doctype": "Item Variant Attribute",
                "name": frappe.generate_hash(length=10),
                "parent": item_code,
                "parenttype": "Item",
                "parentfield": "attributes",
                "idx": idx,
                "attribute": attribute,
                "attribute_value": value,
                "field_name": field_name,
                "use_in_description": use_in_description,
            }
        ).db_insert()


def item_doc(name, variant_of=None, long_desc=None):
    """The fields of an Item doc that on_item_update reads."""
    return SimpleNamespace(name=name, variant_of=variant_of, flags=frappe._dict(web_long_description=long_desc))
