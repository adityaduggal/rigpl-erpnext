from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.manufacturing_rigpl.doctype.process_sheet.process_sheet import ProcessSheet
from rigpl_erpnext.manufacturing_rigpl.utils.bom_template_merge_utils import (
    get_merge_hint,
    item_list_change,
    level_signature,
    merge_hint_html,
    normalise_rule,
    process_signature,
    template_differences,
    work_signature,
)


def rule(attribute, allowed="", numeric=0, formula="", source=None):
    return frappe._dict(attribute=attribute, allowed_values=allowed, is_numeric=numeric, rule=formula,
        value_source=source)


def template(name, fg_quality="C-1X", rm_quality="C-1X", d1_allow="1.5", ops=("ROD Cutting", "Round FG", "Marking"),
             fg_extra=()):
    return frappe._dict(
        name=name, formula="int( qty / int( ( rm_oal + 6 ) / fg_oal ) )", no_of_rm_items=1, length_formula=1,
        operations=[frappe._dict(operation=op) for op in ops],
        fg_restrictions=[rule("Base Material", "Carbide"), rule("Carbide Quality", fg_quality), *fg_extra],
        rm_restrictions=[rule("Carbide Quality", rm_quality),
                         rule("d1_mm", numeric=1, formula=f"rm_d1_mm < fg_d1_mm + {d1_allow}")],
        wip_restrictions=[], fg_rm_map=[],
    )


class TestWorkSignature(FrappeTestCase):
    def test_fg_values_are_not_in_the_signature(self):
        self.assertEqual(work_signature(template("A", "C-1X")), work_signature(template("B", "C-3X")))

    def test_rm_values_are_not_in_the_signature_but_in_the_differences(self):
        a, b = template("A"), template("B", rm_quality="RC-XF1")
        self.assertEqual(work_signature(a), work_signature(b))
        self.assertEqual(template_differences(a, b), ["RM Carbide Quality: RC-XF1 (here: C-1X)"])

    def test_numbers_only_differ_is_almost(self):
        a, b = template("A"), template("B", d1_allow="0.5")
        self.assertNotEqual(work_signature(a), work_signature(b))
        self.assertEqual(work_signature(a, almost=True), work_signature(b, almost=True))
        self.assertEqual(level_signature(a, "Almost"), level_signature(b, "Almost"))
        self.assertEqual(template_differences(a, b),
            ["RM rules: rm_d1_mm<fg_d1_mm+0.5 (here: rm_d1_mm<fg_d1_mm+1.5)"])

    def test_same_operations_level(self):
        a, b = template("A"), template("B", ops=("ROD Cutting", "Round FG"))
        self.assertNotEqual(process_signature(a), process_signature(b))
        b.operations.append(frappe._dict(operation="Marking"))
        b.rm_restrictions.append(rule("Is RM", "Yes"))
        self.assertNotEqual(work_signature(a, almost=True), work_signature(b, almost=True))
        self.assertEqual(level_signature(a, "Same Operations"), level_signature(b, "Same Operations"))

    def test_value_source_is_in_the_signature(self):
        a, b = template("A"), template("B")
        b.wip_restrictions = [rule("Carbide Quality", source="Same as RM")]
        a.wip_restrictions = [rule("Carbide Quality", source="Same as FG")]
        self.assertNotEqual(work_signature(a), work_signature(b))

    def test_normalise_rule(self):
        self.assertEqual(normalise_rule(" rm_d1_mm  ==  fg_d1_mm + 1.5 "), "rm_d1_mm==fg_d1_mm+1.5")
        self.assertEqual(normalise_rule("rm_d1_mm == fg_d1_mm + 1.5", almost=True), "rm_d1_mm==fg_d1_mm+#")


class TestItemListChange(FrappeTestCase):
    def test_changes(self):
        self.assertEqual(item_list_change("Operations", ["A", "B"], ["A"]), "Operations: A (was A > B)")
        self.assertEqual(item_list_change("RM", ["R1", "R2"], ["R2", "R3"]), "RM: 1 not given: R1; 1 new: R3")
        many = [f"R{i}" for i in range(7)]
        self.assertEqual(item_list_change("WIP", many, []), "WIP: 7 not given: R0, R1, R2, R3, R4 and 2 more")


NO_COAT = ("ROD Cutting", "CNC Grinding", "Marking")
COAT = ("ROD Cutting", "CNC Grinding", "Coating", "Marking")


def hint(*templates):
    return merge_hint_html({bt.name: bt for bt in templates}, [bt.name for bt in templates])


class TestMergeHint(FrappeTestCase):
    def test_no_hint(self):
        self.assertIsNone(hint(template("A")))
        self.assertIsNone(hint(template("A"), template("B", ops=("ROD Cutting", "Marking", "Round FG"))))

    def test_fg_values_and_merged_rule(self):
        html = hint(template("A", "C-1X"), template("B", "C-3X"))
        self.assertIn('RIGPL/A"', html)
        self.assertIn('RIGPL/B"', html)
        self.assertIn("C-1X in A, C-3X in B", html)
        self.assertIn("<b>Carbide Quality: C-1X / C-3X</b>", html)
        self.assertNotIn("Operation condition", html)

    def test_duplicates(self):
        self.assertIn("duplicates", hint(template("A"), template("B")))

    def test_rm_difference(self):
        html = hint(template("A"), template("B", "C-3X", rm_quality="RC-XF1"))
        self.assertIn("B: RM Carbide Quality: RC-XF1 (here: C-1X) (A)", html)

    def test_operation_condition(self):
        a = template("A", ops=NO_COAT, fg_extra=[rule("Special Treatment", "None")])
        b = template("B", ops=COAT, fg_extra=[rule("Special Treatment", "TiAlN"), rule("Special Treatment", "AlTiN")])
        html = hint(a, b)
        self.assertIn("<b>Coating: only when Special Treatment Not In None</b>", html)
        self.assertIn("<b>Special Treatment: AlTiN / None / TiAlN</b>", html)
        self.assertNotIn("Operations, formula", html)

    def test_operation_condition_when_the_other_has_any_value(self):
        a = template("A", ops=NO_COAT, fg_extra=[rule("Special Treatment", "None")])
        self.assertIn("<b>Coating: only when Special Treatment Not In None</b>", hint(a, template("B", ops=COAT)))

    def test_operation_condition_without_a_separating_attribute(self):
        a = template("A", ops=NO_COAT, fg_extra=[rule("Special Treatment", "None")])
        b = template("B", ops=COAT, fg_extra=[rule("Special Treatment", "None")])
        html = hint(a, b)
        self.assertIn("Coating is only in B", html)
        self.assertNotIn("only when", html)

    def test_operations_in_another_order_do_not_merge(self):
        self.assertIsNone(hint(template("A", ops=("X", "Y")), template("B", ops=("Y", "X", "Z"))))

    def test_pass_1_group_is_not_shown_again(self):
        html = hint(template("A", "C-1X", ops=NO_COAT), template("B", "C-3X", ops=NO_COAT), template("C", ops=COAT))
        self.assertIn("C-1X / C-3X", html)
        self.assertNotIn('RIGPL/C"', html)
        self.assertNotIn("Operation condition", html)

    def test_get_merge_hint_with_1_template_runs_no_query(self):
        with assert_max_queries(0, test_case=self):
            self.assertIsNone(get_merge_hint(["A"]))


MERGE_HINT = "rigpl_erpnext.manufacturing_rigpl.utils.bom_template_merge_utils.get_merge_hint"
PS = "rigpl_erpnext.manufacturing_rigpl.doctype.process_sheet.process_sheet"


class TestShowMergeHint(FrappeTestCase):
    def run_hint(self, total, hint_html=None):
        ps = frappe._dict(total_applicable_bom_templates=total, production_item="I", sales_order_item=None)
        with patch(f"{PS}.get_bom_template_from_item", return_value=["A", "B"]) as lookup, \
                patch(f"{PS}.frappe.get_doc"), \
                patch(MERGE_HINT, return_value=hint_html), \
                patch(f"{PS}.frappe.msgprint") as msgprint:
            ProcessSheet.show_merge_hint(ps)
        return lookup, msgprint

    def test_one_template(self):
        lookup, msgprint = self.run_hint(1, "<p>x</p>")
        lookup.assert_not_called()
        msgprint.assert_not_called()

    def test_message(self):
        _lookup, msgprint = self.run_hint(2, "<p>x</p>")
        msgprint.assert_called_once_with("<p>x</p>", title="These BOM Templates Can Merge", indicator="blue")

    def test_no_message_without_a_hint(self):
        self.run_hint(2)[1].assert_not_called()
