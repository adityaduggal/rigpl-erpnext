import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.manufacturing_rigpl.utils.bom_template_merge_utils import (
    item_list_change,
    level_signature,
    normalise_rule,
    process_signature,
    template_differences,
    work_signature,
)


def rule(attribute, allowed="", numeric=0, formula="", source=None):
    return frappe._dict(attribute=attribute, allowed_values=allowed, is_numeric=numeric, rule=formula,
        value_source=source)


def template(name, fg_quality="C-1X", rm_quality="C-1X", d1_allow="1.5", ops=("ROD Cutting", "Round FG", "Marking")):
    return frappe._dict(
        name=name, formula="int( qty / int( ( rm_oal + 6 ) / fg_oal ) )", no_of_rm_items=1, length_formula=1,
        operations=[frappe._dict(operation=op) for op in ops],
        fg_restrictions=[rule("Base Material", "Carbide"), rule("Carbide Quality", fg_quality)],
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
