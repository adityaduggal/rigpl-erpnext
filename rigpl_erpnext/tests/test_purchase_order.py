from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.validations import purchase_order as po
from rigpl_erpnext.tests.test_variant_table import insert_item
from rigpl_erpnext.utils.item_attribute_utils import get_attribute_rows

SUPPLIER = "_Test RIGPL PO Supplier"
TEMPLATE = "_Test RIGPL PO Template"
VARIANT = "_Test RIGPL PO Variant"
SPECIAL = "_Test RIGPL PO Special"
SO_ITEM = "_Test RIGPL PO SO Item"


def att(attribute, value):
    return frappe._dict(attribute=attribute, attribute_value=value)


def rule(attribute, allowed=None, formula=None):
    return frappe._dict(attribute=attribute, allowed_values=allowed, is_numeric=1 if formula else 0,
                        rule=formula, formula=formula)


def prule(name, rate, attributes):
    return frappe._dict(name=name, rate=rate, attributes=attributes)


def row(idx, **kwargs):
    values = dict(idx=idx, item_code="IT-OLD", reference_dt=po.JC_DOCTYPE, reference_dn=None, so_detail=None,
                  subcontracted_item=None, description=None, gst_hsn_code=None, qty=1, uom="Nos",
                  conversion_factor=1, price_list_rate=0)
    values.update(kwargs)
    return frappe._dict(values)


def item(name, job_work=0, purchase=1, hsn="8207", description=None, variant_of=None):
    return frappe._dict(name=name, is_job_work=job_work, is_purchase_item=purchase, customs_tariff_number=hsn,
                        description=description or name, stock_uom="Nos", variant_of=variant_of)


ITEM = [att("Base Material", "HSS"), att("Tool Type", "Drill"), att("d1_mm", "6")]


class TestRuleMatches(FrappeTestCase):
    def test_text_rules(self):
        self.assertTrue(po.rule_matches([rule("Base Material", "HSS"), rule("Tool Type", "Drill")], ITEM))
        self.assertFalse(po.rule_matches([rule("Base Material", "HSS"), rule("Tool Type", "Reamer")], ITEM))

    def test_missing_attribute_does_not_match(self):
        self.assertFalse(po.rule_matches([rule("Series", "C3HS")], ITEM))

    def test_numeric_rule(self):
        self.assertTrue(po.rule_matches([rule("d1_mm", formula="d1_mm >= 5")], ITEM))
        self.assertFalse(po.rule_matches([rule("d1_mm", formula="d1_mm > 10")], ITEM))

    def test_formula_without_item_attribute_does_not_match(self):
        self.assertFalse(po.rule_matches([rule("l1_mm", formula="l1_mm > 1")], ITEM))

    def test_empty_rule_does_not_match(self):
        self.assertFalse(po.rule_matches([], ITEM))

    def test_first_matching_rule_wins(self):
        rules = [
            prule("PR1", 10, [rule("Tool Type", "Reamer")]),
            prule("PR2", 20, [rule("Base Material", "HSS")]),
            prule("PR3", 30, [rule("Tool Type", "Drill")]),
        ]
        self.assertEqual(po.find_rule_rate(rules, ITEM), 20)
        self.assertIsNone(po.find_rule_rate(rules[:1], ITEM))


class TestJobCardQty(FrappeTestCase):
    def test_same_uom_uses_qty(self):
        self.assertEqual(po.jc_completed_qty(row(1, qty=5), "Nos"), 5)

    def test_other_uom_or_factor_uses_conversion_factor(self):
        self.assertEqual(po.jc_completed_qty(row(1, qty=5, uom="Kg", conversion_factor=1), "Nos"), 1)
        self.assertEqual(po.jc_completed_qty(row(1, qty=5, conversion_factor=3), "Nos"), 3)

    def test_submitted_job_card_with_other_qty_throws(self):
        doc = SimpleNamespace(name="_Test RIGPL PO", doctype="Purchase Order",
                           items=[row(1, reference_dn="JC-1", subcontracted_item="SUB-1", qty=5)])
        jc = frappe._dict(name="JC-1", docstatus=1, status="Completed", total_completed_qty=4)
        data = frappe._dict(job_cards={"JC-1": jc}, item_map={"SUB-1": item("SUB-1")})
        with self.assertRaises(frappe.ValidationError) as error:
            po.validate_job_cards(doc, data)
        self.assertIn("from 5.0 to 4.0", str(error.exception))
        doc.items[0].qty = 4
        po.validate_job_cards(doc, data)


class TestCheckSubcontracting(FrappeTestCase):
    def data(self):
        jc = frappe._dict(name="JC-1", operation="OP-1", production_item="FG-1", description="JC description")
        return frappe._dict(
            job_cards={"JC-1": jc, "JC-2": frappe._dict(jc, name="JC-2")},
            operations={"OP-1": frappe._dict(name="OP-1", sub_contracting_item_code="IT-JW")},
            item_map={
                "IT-OLD": item("IT-OLD", job_work=0, hsn="1111"),
                "IT-JW": item("IT-JW", job_work=1, hsn="9988"),
                "FG-1": item("FG-1"),
                "SUB-1": item("SUB-1", description="Sub item description"),
            },
        )

    def test_item_is_replaced_before_job_work_check(self):
        doc = SimpleNamespace(name="PO-1", is_subcontracting=1,
                           items=[row(1, reference_dn="JC-1", subcontracted_item="SUB-1")])
        po.check_subcontracting(doc, self.data())
        d = doc.items[0]
        self.assertEqual((d.item_code, d.gst_hsn_code, d.description), ("IT-JW", "9988", "Sub item description"))

    def test_so_detail_takes_job_card_item(self):
        doc = SimpleNamespace(name="PO-1", is_subcontracting=1, items=[row(1, reference_dn="JC-1", so_detail="SOI-1")])
        po.check_subcontracting(doc, self.data())
        self.assertEqual((doc.items[0].subcontracted_item, doc.items[0].description), ("FG-1", "JC description"))

    def test_empty_subcontracted_item_gives_mandatory_error(self):
        doc = SimpleNamespace(name="PO-1", is_subcontracting=1, items=[row(1, reference_dn="JC-1")])
        with self.assertRaisesRegex(frappe.ValidationError, "Subcontracted Item is Mandatory"):
            po.check_subcontracting(doc, self.data())

    def test_duplicate_job_card(self):
        items = [row(1, reference_dn="JC-1", subcontracted_item="SUB-1"),
                 row(2, reference_dn="JC-2", subcontracted_item="SUB-1"),
                 row(3, reference_dn="JC-1", subcontracted_item="SUB-1")]
        doc = SimpleNamespace(name="PO-1", is_subcontracting=1, items=items)
        with self.assertRaisesRegex(frappe.ValidationError, "Row# 1 and Row# 3"):
            po.check_subcontracting(doc, self.data())

    def test_operation_without_subcontracting_item(self):
        data = self.data()
        data.operations["OP-1"].sub_contracting_item_code = None
        doc = SimpleNamespace(name="PO-1", is_subcontracting=1,
                           items=[row(1, reference_dn="JC-1", subcontracted_item="SUB-1")])
        with self.assertRaisesRegex(frappe.ValidationError, "no Sub Contracting Item Code"):
            po.check_subcontracting(doc, data)


def insert_pricing_rule(name, priority, rate, attributes):
    frappe.get_doc({
        "doctype": "Pricing Rule", "name": name, "title": name, "apply_on": "Attributes", "buying": 1,
        "applicable_for": "Supplier", "supplier": SUPPLIER, "disable": 0, "valid_from": "2020-01-01",
        "priority": priority, "rate": rate,
    }).db_insert()
    for idx, (attribute, value) in enumerate(attributes, start=1):
        frappe.get_doc({
            "doctype": "Item Variant Restrictions", "name": frappe.generate_hash(length=10), "parent": name,
            "parenttype": "Pricing Rule", "parentfield": "attributes", "idx": idx, "attribute": attribute,
            "allowed_values": value, "is_numeric": 0,
        }).db_insert()


def insert_mto(name, item_code, so_item, attributes):
    frappe.get_doc({"doctype": po.MTO_DOCTYPE, "name": name, "item_code": item_code,
                    "sales_order_item": so_item, "docstatus": 1}).db_insert()
    for idx, (attribute, value) in enumerate(attributes, start=1):
        frappe.get_doc({
            "doctype": "Item Variant Attribute", "name": frappe.generate_hash(length=10), "parent": name,
            "parenttype": po.MTO_DOCTYPE, "parentfield": "attributes", "idx": idx, "attribute": attribute,
            "attribute_value": value,
        }).db_insert()


class TestPricingQueries(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        insert_pricing_rule("_Test RIGPL PR 19", "19", 19, [("Base Material", "HSS")])
        insert_pricing_rule("_Test RIGPL PR 20 B", "20", 22, [("Base Material", "HSS"), ("Tool Type", "Drill")])
        insert_pricing_rule("_Test RIGPL PR 20 A", "20", 21, [("Base Material", "Carbide")])
        insert_item(TEMPLATE)
        insert_item(VARIANT, variant_of=TEMPLATE, attributes=[("Base Material", "HSS"), ("Tool Type", "Drill")])
        insert_item(SPECIAL)
        insert_mto("_Test RIGPL PO MTO", SPECIAL, SO_ITEM, [("Base Material", "Carbide")])

    def test_rules_by_priority_with_attributes_in_two_queries(self):
        with assert_max_queries(2, test_case=self):
            rules = po.get_supplier_attribute_rules(SUPPLIER)
        self.assertEqual([r.name for r in rules],
                         ["_Test RIGPL PR 20 A", "_Test RIGPL PR 20 B", "_Test RIGPL PR 19"])
        self.assertEqual([a.attribute for a in rules[1].attributes], ["Base Material", "Tool Type"])

    def test_row_attributes_from_item_and_made_to_order(self):
        doc = SimpleNamespace(items=[row(1, subcontracted_item=VARIANT), row(2, subcontracted_item=SPECIAL,
                                                                          so_detail=SO_ITEM)])
        items = {VARIANT: item(VARIANT, variant_of=TEMPLATE), SPECIAL: item(SPECIAL)}
        with assert_max_queries(3, test_case=self):
            rows = po.get_row_attributes(doc, items)
        self.assertEqual([a.attribute_value for a in rows[(VARIANT, None)]], ["HSS", "Drill"])
        self.assertEqual([a.attribute_value for a in rows[(SPECIAL, SO_ITEM)]], ["Carbide"])
        rules = po.get_supplier_attribute_rules(SUPPLIER)
        self.assertEqual(po.find_rule_rate(rules, rows[(VARIANT, None)]), 22)
        self.assertEqual(po.find_rule_rate(rules, rows[(SPECIAL, SO_ITEM)]), 21)

    def test_special_item_without_made_to_order_throws(self):
        doc = SimpleNamespace(items=[row(3, subcontracted_item=SPECIAL, so_detail="_Test RIGPL PO Other SO")])
        with self.assertRaisesRegex(frappe.ValidationError, "Row# 3"):
            po.get_row_attributes(doc, {SPECIAL: item(SPECIAL)})

    def test_attribute_rows_by_parenttype(self):
        self.assertEqual(get_attribute_rows(["_Test RIGPL PO MTO"]), {})
        rows = get_attribute_rows(["_Test RIGPL PO MTO"], parenttype=po.MTO_DOCTYPE)
        self.assertEqual([a.attribute for a in rows["_Test RIGPL PO MTO"]], ["Base Material"])
