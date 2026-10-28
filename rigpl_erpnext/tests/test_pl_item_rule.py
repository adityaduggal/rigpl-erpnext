from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.rigpl_erpnext.validations.item import validate_pl_item_rule
from rigpl_erpnext.tests.test_variant_table import insert_item
from rigpl_erpnext.website_rigpl.item_sync import get_pl_item_mismatches, on_item_update

TEMPLATE = "_Test RIGPL PL Template"
VARIANT = "_Test RIGPL PL Variant"
OTHER_VARIANT = "_Test RIGPL PL Variant 2"


class TestPlItemRule(FrappeTestCase):
    def setUp(self):
        insert_item(TEMPLATE)
        insert_item(VARIANT, variant_of=TEMPLATE)
        insert_item(OTHER_VARIANT, variant_of=TEMPLATE)

    def tearDown(self):
        frappe.db.rollback()

    def set_pl_item(self, **values):
        for name, pl_item in values.items():
            frappe.db.set_value("Item", name, "pl_item", pl_item, update_modified=False)

    def item(self, name, **changes):
        doc = frappe.get_doc("Item", name)
        doc.update(changes)
        return doc

    def test_variant_cannot_be_pl_item_under_template_that_is_not(self):
        self.set_pl_item(**{TEMPLATE: 0})
        with self.assertRaises(frappe.ValidationError):
            validate_pl_item_rule(self.item(VARIANT, pl_item=1))

    def test_variant_can_be_pl_item_or_not_under_pl_template(self):
        self.set_pl_item(**{TEMPLATE: 1})
        validate_pl_item_rule(self.item(VARIANT, pl_item=1))
        validate_pl_item_rule(self.item(VARIANT, pl_item=0))

    def test_template_cannot_stop_being_pl_item_while_variants_are(self):
        self.set_pl_item(**{TEMPLATE: 1, VARIANT: 1})
        with self.assertRaises(frappe.ValidationError):
            validate_pl_item_rule(self.item(TEMPLATE, pl_item=0))

    def test_template_can_stop_being_pl_item_when_no_variant_is(self):
        self.set_pl_item(**{TEMPLATE: 1})
        doc = self.item(TEMPLATE, pl_item=0)
        validate_pl_item_rule(doc)
        self.assertIsNone(doc.flags.variants_to_unlist)

    def test_disabled_template_turns_off_pl_item_on_its_variants(self):
        self.set_pl_item(**{TEMPLATE: 1, VARIANT: 1})
        doc = self.item(TEMPLATE, pl_item=0, disabled=1)
        validate_pl_item_rule(doc)
        self.assertEqual(doc.flags.variants_to_unlist, [VARIANT])

        frappe.db.set_value("Item", TEMPLATE, {"pl_item": 0, "disabled": 1}, update_modified=False)
        on_item_update(
            SimpleNamespace(name=TEMPLATE, variant_of=None, flags=frappe._dict(variants_to_unlist=[VARIANT]))
        )
        self.assertEqual(frappe.db.get_value("Item", VARIANT, "pl_item"), 0)

    def test_mismatch_report_lists_template_with_count(self):
        self.set_pl_item(**{TEMPLATE: 0, VARIANT: 1, OTHER_VARIANT: 1})
        rows = {row.name: row.variants for row in get_pl_item_mismatches()}
        self.assertEqual(rows.get(TEMPLATE), 2)

        self.set_pl_item(**{TEMPLATE: 1})
        self.assertNotIn(TEMPLATE, {row.name for row in get_pl_item_mismatches()})
