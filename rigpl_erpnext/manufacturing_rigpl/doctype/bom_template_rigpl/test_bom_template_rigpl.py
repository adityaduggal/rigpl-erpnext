# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Private Limited and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
from frappe.tests.utils import FrappeTestCase


def make_template(**tables):
    return frappe.get_doc(dict(doctype="BOM Template RIGPL", **tables))


def map_row(fg_value="x", rm_attribute="Base Material", fg_attribute="Base Material"):
    return {"fg_attribute": fg_attribute, "fg_value": fg_value, "rm_attribute": rm_attribute, "rm_values": "y"}


class TestBOMTemplateRIGPL(FrappeTestCase):
    def test_value_source_only_on_rm_and_wip_text_rules(self):
        bt = make_template(fg_restrictions=[{"attribute": "Base Material", "value_source": "Same as FG"}])
        self.assertRaises(frappe.ValidationError, bt.validate_restriction_rules, "fg_restrictions")
        bt = make_template(rm_restrictions=[{"attribute": "d1_mm", "value_source": "Same as FG"}])
        self.assertRaises(frappe.ValidationError, bt.validate_restriction_rules, "rm_restrictions")
        bt = make_template(rm_restrictions=[{"attribute": "Base Material", "value_source": "Same as RM"}])
        self.assertRaises(frappe.ValidationError, bt.validate_restriction_rules, "rm_restrictions")
        bt = make_template(wip_restrictions=[{"attribute": "Base Material", "value_source": "Same as RM"}])
        bt.validate_restriction_rules("wip_restrictions")

    def test_value_source_clears_allowed_values(self):
        bt = make_template(rm_restrictions=[{"attribute": "Base Material", "allowed_values": "x",
            "value_source": "Same as FG"}])
        bt.validate_restriction_rules("rm_restrictions")
        self.assertEqual(bt.rm_restrictions[0].allowed_values, "")

    def test_value_source_row_must_be_alone(self):
        bt = make_template(rm_restrictions=[{"attribute": "Base Material", "value_source": "Same as FG"},
            {"attribute": "Base Material", "allowed_values": "x"}])
        self.assertRaises(frappe.ValidationError, bt.validate_restriction_rules, "rm_restrictions")

    def test_rm_map_checks(self):
        # Duplicate row
        self.assertRaises(frappe.ValidationError, make_template(fg_rm_map=[map_row(), map_row()]).validate_rm_map)
        # 2 FG attributes for 1 RM attribute
        bt = make_template(fg_rm_map=[map_row(), map_row(fg_attribute="Tool Type")])
        self.assertRaises(frappe.ValidationError, bt.validate_rm_map)
        # The mapped RM attribute also has RM rule rows
        bt = make_template(fg_rm_map=[map_row()], rm_restrictions=[{"attribute": "Base Material", "is_numeric": 0}])
        self.assertRaises(frappe.ValidationError, bt.validate_rm_map)
        # An FG value of the FG rules has no map row
        bt = make_template(fg_rm_map=[map_row("x")], fg_restrictions=[
            {"attribute": "Base Material", "allowed_values": "x"}, {"attribute": "Base Material", "allowed_values": "z"}])
        self.assertRaises(frappe.ValidationError, bt.validate_rm_map)
        bt.append("fg_rm_map", map_row("z"))
        bt.validate_rm_map()

    def test_title_joins_repeated_rows(self):
        bt = make_template(fg_restrictions=[{"attribute": "_Test RIGPL A", "allowed_values": "X"},
            {"attribute": "_Test RIGPL A", "allowed_values": "Y"}, {"attribute": "d1_mm", "is_numeric": 1}])
        bt.generate_title()
        self.assertEqual(bt.title, "X / Y, Rules For: d1_mm")

    def test_operation_conditions(self):
        condition = {"condition_attribute": "Base Material", "condition_type": "Not In", "condition_values": "x"}
        for flags in ({"final_operation": 1}, {"allow_consumption_of_rm": 1}):
            bt = make_template(operations=[dict(condition, operation="Coating", **flags)])
            self.assertRaises(frappe.ValidationError, bt.validate_operation_conditions)
        bt = make_template(operations=[{"operation": "Coating", "condition_attribute": "Base Material"}])
        self.assertRaises(frappe.ValidationError, bt.validate_operation_conditions)
        bt = make_template(operations=[dict(condition, operation="Coating", condition_attribute="d1_mm")])
        self.assertRaises(frappe.ValidationError, bt.validate_operation_conditions)
