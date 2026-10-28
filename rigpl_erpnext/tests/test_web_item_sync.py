from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.tests.test_variant_table import insert_item, insert_website_item
from rigpl_erpnext.website_rigpl.item_sync import (
    make_missing_web_items,
    on_item_update,
    plan_web_item_changes,
    set_web_long_description,
    sync_web_items,
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

    def test_long_description_writes_only_a_difference(self):
        self.assertTrue(set_web_long_description(VARIANT, "Dia 10 mm"))
        self.assertFalse(set_web_long_description(VARIANT, "Dia 10 mm"))
        self.assertFalse(set_web_long_description("_Test RIGPL No Web Item", "Dia 10 mm"))


def item_doc(name, variant_of=None, long_desc=None):
    """The fields of an Item doc that on_item_update reads."""
    return SimpleNamespace(name=name, variant_of=variant_of, flags=frappe._dict(web_long_description=long_desc))
