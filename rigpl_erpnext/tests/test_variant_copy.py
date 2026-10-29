from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.scheduled_tasks import variant_copy as vc
from rigpl_erpnext.tests.test_variant_table import insert_item, insert_website_item
from rigpl_erpnext.utils.item_utils import generate_description, make_description

TEMPLATE = "_Test RIGPL VC Template"
MATERIAL = "_Test RIGPL VC Material"  # text attribute
D1 = "_Test RIGPL VC d1"  # numeric attribute
COMPANY = "_Test RIGPL VC Company"
OLD_DATE = "2020-01-01 00:00:00"


def row(attribute, value=None, idx=1, use=1, prefix='""', suffix='""'):
    return frappe._dict(
        attribute=attribute, attribute_value=value, idx=idx, use_in_description=use, prefix=prefix, suffix=suffix
    )


def template_rows(*rows):
    return {r.attribute: r for r in rows}


VALUES = {(MATERIAL, "carbide"): ('"Carbide"', '"Solid Carbide"')}


def default_row(company=COMPANY, **values):
    """An Item Default row with all the fields that the job copies."""
    row = frappe._dict({field: None for field in vc.DEFAULT_FIELDS}, company=company)
    row.update(values)
    return row


class TestMakeDescription(FrappeTestCase):
    def make(self, variant_rows, rows, numeric=(D1,)):
        return make_description(variant_rows, template_rows(*rows), set(numeric), VALUES)

    def test_text_with_prefix_and_suffix(self):
        result = self.make([row(MATERIAL, "Carbide")], [row(MATERIAL, prefix='"M:"', suffix='" "')])
        self.assertEqual(result, ("M:Carbide ", "M:Solid Carbide "))

    def test_text_without_prefix(self):
        self.assertEqual(self.make([row(MATERIAL, "Carbide")], [row(MATERIAL)]), ("Carbide", "Solid Carbide"))

    def test_numeric_value(self):
        result = self.make([row(D1, "6.50")], [row(D1, prefix='"D"', suffix='"mm"')])
        self.assertEqual(result, ("D6.5mm", "D6.5mm"))

    def test_numeric_zero_is_left_out(self):
        self.assertEqual(self.make([row(D1, "0")], [row(D1, prefix='"D"', suffix='"mm"')]), ("", ""))

    def test_attribute_not_used_in_description(self):
        self.assertEqual(self.make([row(MATERIAL, "Carbide")], [row(MATERIAL, use=0)]), ("", ""))

    def test_order_is_variant_idx(self):
        variant_rows = [row(D1, "6", idx=2), row(MATERIAL, "Carbide", idx=1)]
        result = self.make(variant_rows, [row(MATERIAL, suffix='" "'), row(D1)])
        self.assertEqual(result, ("Carbide 6", "Solid Carbide 6"))

    def test_value_matches_without_case_and_trailing_space(self):
        self.assertEqual(self.make([row(MATERIAL, "CARBIDE ")], [row(MATERIAL)])[0], "Carbide")

    def test_missing_value_throws(self):
        with self.assertRaises(frappe.ValidationError):
            self.make([row(MATERIAL, "Steel")], [row(MATERIAL)])


def plan_inputs(variants, variant_rows=None, item_default=None, defaults=None, variant_limit=10):
    template = frappe._dict(
        name=TEMPLATE,
        warranty_period="12",
        variant_limit=variant_limit,
        variant_count=len(variants),
        item_default=item_default or default_row(),
    )
    data = frappe._dict(
        variants=variants,
        attributes={v.name: variant_rows or [row(D1, "6")] for v in variants},
        defaults=defaults or {},
        web_items={},
        description_data=({TEMPLATE: template_rows(row(D1))}, {D1}, {}),
    )
    return template, data


def variant(name, warranty="12", description="6", published=0, image=None):
    return frappe._dict(
        name=name, warranty_period=warranty, description=description, published_in_website=published, image=image
    )


class TestPlanVariantChanges(FrappeTestCase):
    def plan(self, *args, **kwargs):
        return vc.plan_variant_changes(*plan_inputs(*args, **kwargs), ["warranty_period"])

    def test_matching_variant_has_no_changes(self):
        plan = self.plan([variant("V1")])
        self.assertEqual((plan.item_changes, plan.default_changes, plan.errors), ({}, {}, []))

    def test_only_different_fields_change(self):
        plan = self.plan([variant("V1"), variant("V2", warranty="6")])
        self.assertEqual(plan.item_changes, {"V2": {"warranty_period": "12"}})

    def test_description_and_item_name_change_together(self):
        plan = self.plan([variant("V1", description="old")])
        self.assertEqual(plan.item_changes, {"V1": {"description": "6", "item_name": "6"}})

    def test_wrong_attribute_order_is_an_error(self):
        plan = self.plan([variant("V1", warranty="6")], variant_rows=[row(MATERIAL, "Carbide")])
        self.assertEqual(plan.item_changes, {})
        self.assertEqual(plan.errors, [("V1", f"Row# 1 should have {D1} as per the template")])

    def test_published_variant_without_image_is_an_error(self):
        plan = self.plan([variant("V1", warranty="6", published=1)])
        self.assertEqual(plan.item_changes, {})
        self.assertEqual(len(plan.errors), 1)

    def test_over_variant_limit_skips_template(self):
        plan = self.plan([variant("V1", warranty="6"), variant("V2", warranty="6")], variant_limit=1)
        self.assertEqual(plan.item_changes, {})
        self.assertEqual([name for name, _ in plan.errors], [TEMPLATE])

    def test_template_without_item_defaults_skips_template(self):
        template, data = plan_inputs([variant("V1", warranty="6")])
        template.item_default = None
        plan = vc.plan_variant_changes(template, data, ["warranty_period"])
        self.assertEqual(plan.item_changes, {})
        self.assertEqual(plan.errors, [(TEMPLATE, "Item Defaults are Mandatory for Template")])

    def test_different_item_default_is_copied(self):
        defaults = {"V1": default_row("Other", name="D1")}
        plan = self.plan([variant("V1")], defaults=defaults)
        self.assertEqual(plan.default_changes["D1"]["company"], COMPANY)


def insert_attribute(name, numeric, values=()):
    frappe.get_doc(
        doctype="Item Attribute", name=name, attribute_name=name, numeric_values=numeric
    ).db_insert()
    for idx, (value, desc, long_desc) in enumerate(values, 1):
        frappe.get_doc(
            doctype="Item Attribute Value",
            name=frappe.generate_hash(length=10),
            parent=name,
            parenttype="Item Attribute",
            parentfield="item_attribute_values",
            idx=idx,
            attribute_value=value,
            abbr=value,
            description=desc,
            long_description=long_desc,
        ).db_insert()


def insert_attribute_row(parent, attribute, value, idx, prefix='""', suffix='""'):
    frappe.get_doc(
        doctype="Item Variant Attribute",
        name=frappe.generate_hash(length=10),
        parent=parent,
        parenttype="Item",
        parentfield="attributes",
        idx=idx,
        attribute=attribute,
        attribute_value=value,
        use_in_description=1,
        prefix=prefix,
        suffix=suffix,
    ).db_insert()


def insert_item_default(parent, company=COMPANY):
    frappe.get_doc(
        doctype="Item Default",
        name=frappe.generate_hash(length=10),
        parent=parent,
        parenttype="Item",
        parentfield="item_defaults",
        idx=1,
        company=company,
    ).db_insert()


def insert_template(variant_limit=100):
    insert_item(TEMPLATE)
    insert_attribute_row(TEMPLATE, MATERIAL, None, 1, suffix='" "')
    insert_attribute_row(TEMPLATE, D1, None, 2, prefix='"D"')
    insert_item_default(TEMPLATE)
    frappe.db.set_value("Item", TEMPLATE, {"variant_limit": variant_limit, "warranty_period": "12"},
        update_modified=False)


def insert_variant(name, d1="6", warranty="12"):
    """A variant that matches the template unless `warranty` is different."""
    insert_item(name, variant_of=TEMPLATE)
    insert_attribute_row(name, MATERIAL, "Carbide", 1)
    insert_attribute_row(name, D1, d1, 2)
    insert_item_default(name)
    frappe.db.set_value("Item", name, {
        "warranty_period": warranty,
        "description": f"Carbide D{d1}",
        "item_name": f"Solid Carbide D{d1}",
        "modified": OLD_DATE,
    }, update_modified=False)


class TestSyncVariantsFromTemplates(FrappeTestCase):
    def setUp(self):
        insert_attribute(MATERIAL, 0, [("Carbide", '"Carbide"', '"Solid Carbide"')])
        insert_attribute(D1, 1)
        insert_template()

    def tearDown(self):
        frappe.db.rollback()

    def sync(self):
        with patch.object(vc, "get_variant_copy_fields", return_value=["warranty_period"]), \
                patch.object(vc.frappe.db, "commit"), patch.object(vc.frappe, "log_error") as log_error:
            vc.sync_variants_from_templates([TEMPLATE])
        return log_error

    def test_writes_only_the_variant_that_is_different(self):
        insert_variant("_Test RIGPL VC V1")
        insert_variant("_Test RIGPL VC V2", d1="8", warranty="6")
        insert_website_item("_Test RIGPL VC WEB-V2", "_Test RIGPL VC V2", variant_of=TEMPLATE)

        log_error = self.sync()

        log_error.assert_not_called()
        v1 = frappe.db.get_value("Item", "_Test RIGPL VC V1", ["warranty_period", "modified"], as_dict=True)
        v2 = frappe.db.get_value("Item", "_Test RIGPL VC V2", ["warranty_period", "modified"], as_dict=True)
        self.assertEqual((v1.warranty_period, str(v1.modified)), ("12", OLD_DATE))
        self.assertEqual(v2.warranty_period, "12")
        self.assertGreater(str(v2.modified), OLD_DATE)
        self.assertEqual(frappe.db.count("Version", {"ref_doctype": "Item", "docname": "_Test RIGPL VC V2"}), 1)
        self.assertEqual(frappe.db.count("Version", {"ref_doctype": "Item", "docname": "_Test RIGPL VC V1"}), 0)
        self.assertEqual(
            frappe.db.get_value("Website Item", "_Test RIGPL VC WEB-V2", "web_long_description"), "Solid Carbide D8"
        )

    def test_bad_variant_is_logged_and_others_still_change(self):
        insert_variant("_Test RIGPL VC V1", warranty="6")
        insert_variant("_Test RIGPL VC V2", warranty="6")
        frappe.db.delete("Item Variant Attribute", {"parent": "_Test RIGPL VC V2", "attribute": D1})

        log_error = self.sync()

        log_error.assert_called_once()
        self.assertIn("_Test RIGPL VC V2", log_error.call_args[0][0])
        self.assertEqual(frappe.db.get_value("Item", "_Test RIGPL VC V1", "warranty_period"), "12")
        self.assertEqual(frappe.db.get_value("Item", "_Test RIGPL VC V2", "warranty_period"), "6")

    def test_different_item_default_is_copied(self):
        insert_variant("_Test RIGPL VC V1")
        frappe.db.set_value("Item Default", {"parent": "_Test RIGPL VC V1"}, "company", "Other",
            update_modified=False)

        self.sync()

        self.assertEqual(frappe.db.get_value("Item Default", {"parent": "_Test RIGPL VC V1"}, "company"), COMPANY)
        self.assertGreater(str(frappe.db.get_value("Item", "_Test RIGPL VC V1", "modified")), OLD_DATE)

    def test_query_count_does_not_grow_with_variants(self):
        self.sync()  # loads the meta caches
        counts = []
        for count in (2, 6):
            frappe.db.delete("Item", {"variant_of": TEMPLATE})
            for i in range(count):
                insert_variant(f"_Test RIGPL VC V{count}-{i}", d1=str(i + 1), warranty="6")
            with assert_max_queries(40, test_case=self) as guard:
                self.sync()
            counts.append(guard.count)
        self.assertEqual(counts[0], counts[1])

    def test_generate_description_of_item_doc(self):
        doc = frappe.get_doc({
            "doctype": "Item",
            "variant_of": TEMPLATE,
            "attributes": [
                {"attribute": MATERIAL, "attribute_value": "Carbide", "idx": 1},
                {"attribute": D1, "attribute_value": "6.5", "idx": 2},
            ],
        })
        self.assertEqual(generate_description(doc), ("Carbide D6.5", "Solid Carbide D6.5"))


class TestCheckExpiredItems(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_disables_only_expired_items(self):
        for name, end_of_life in (("_Test RIGPL VC Old 1", "2020-01-01"), ("_Test RIGPL VC Old 2", "2021-01-01"),
                ("_Test RIGPL VC No EOL", None), ("_Test RIGPL VC Future", "2099-12-31")):
            insert_item(name, variant_of=TEMPLATE)
            frappe.db.set_value("Item", name, "end_of_life", end_of_life, update_modified=False)

        with patch.object(vc.frappe.db, "commit"), assert_max_queries(6, test_case=self):
            vc.check_expired_items()

        disabled = dict(frappe.get_all("Item", filters={"name": ("like", "_Test RIGPL VC %")},
            fields=["name", "disabled"], as_list=True))
        self.assertEqual(disabled["_Test RIGPL VC Old 1"], 1)
        self.assertEqual(disabled["_Test RIGPL VC Old 2"], 1)
        self.assertEqual(disabled["_Test RIGPL VC No EOL"], 0)
        self.assertEqual(disabled["_Test RIGPL VC Future"], 0)
