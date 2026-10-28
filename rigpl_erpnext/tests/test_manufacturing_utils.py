
import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.manufacturing_rigpl.utils.job_card_utils import match_existing_job_cards
from rigpl_erpnext.manufacturing_rigpl.utils.manufacturing_utils import (
    get_produced_qty_changes,
    match_bom_templates,
)


def att(attribute, value, numeric=0):
    return frappe._dict(attribute=attribute, attribute_value=value, numeric_values=numeric)


def rule(attribute, allowed="", numeric=0, formula=""):
    return frappe._dict(attribute=attribute, allowed_values=allowed, is_numeric=numeric, rule=formula)


ITEM = [att("Base Material", "HSS"), att("Tool Type", "Drill"), att("d1_mm", "6", numeric=1)]


class TestMatchBomTemplates(FrappeTestCase):
    def test_text_rules(self):
        rules = {
            "BT1": [rule("Base Material", "HSS"), rule("Tool Type", "Drill")],
            "BT2": [rule("Base Material", "HSS"), rule("Tool Type", "Reamer")],
            "BT3": [rule("Base Material", "Carbide")],
        }
        self.assertEqual(match_bom_templates(rules, ITEM), ["BT1"])

    def test_missing_attribute_does_not_match(self):
        rules = {"BT1": [rule("Base Material", "HSS"), rule("Series", "C3HS")]}
        self.assertEqual(match_bom_templates(rules, ITEM), [])

    def test_template_without_rules_matches_all(self):
        self.assertEqual(match_bom_templates({"BT1": []}, ITEM), ["BT1"])
        self.assertEqual(match_bom_templates({"BT1": []}, []), ["BT1"])

    def test_numeric_rule(self):
        rules = {
            "BT1": [rule("Base Material", "HSS"), rule("d1_mm", numeric=1, formula="fg_d1_mm >= 5")],
            "BT2": [rule("Base Material", "HSS"), rule("d1_mm", numeric=1, formula="fg_d1_mm > 10")],
        }
        self.assertEqual(match_bom_templates(rules, ITEM), ["BT1"])

    def test_order_follows_rules(self):
        rules = {"BT2": [rule("Tool Type", "Drill")], "BT1": [rule("Base Material", "HSS")]}
        self.assertEqual(match_bom_templates(rules, ITEM), ["BT2", "BT1"])


def op(operation, consume=0):
    return frappe._dict(operation=operation, allow_consumption_of_rm=consume)


def jc(name, consume=0, transfer=0):
    return frappe._dict(name=name, allow_consumption_of_rm=consume, transfer_entry=transfer)


class TestMatchExistingJobCards(FrappeTestCase):
    def test_transfer_operation_matches_transfer_job_cards(self):
        cards = [jc("JC1", transfer=1), jc("JC2", transfer=0)]
        found = match_existing_job_cards([op("Coating")], "Coating", cards, {}, [])
        self.assertEqual([d.name for d in found], ["JC1"])

    def test_rm_operation_needs_the_same_rm(self):
        cards = [jc("JC1", consume=1), jc("JC2", consume=1), jc("JC3", consume=0)]
        jc_rm = {"JC1": ["RM-A", "RM-B"], "JC2": ["RM-A", "RM-C"]}
        found = match_existing_job_cards([op("Cutting", consume=1)], "Cutting", cards, jc_rm, ["RM-B", "RM-A"])
        self.assertEqual([d.name for d in found], ["JC1"])

    def test_other_operation_and_repeated_rows(self):
        cards = [jc("JC1", transfer=1)]
        ops = [op("Coating"), op("Grinding"), op("Coating")]
        found = match_existing_job_cards(ops, "Coating", cards, {}, [])
        self.assertEqual([d.name for d in found], ["JC1", "JC1"])
        self.assertEqual(match_existing_job_cards(ops, "Marking", cards, {}, []), [])


def sheet(status="Submitted", quantity=100, produced=0, short_closed=0):
    return frappe._dict(status=status, quantity=quantity, produced_qty=produced, short_closed_qty=short_closed)


def card(completed, short_close=0):
    return frappe._dict(total_completed_qty=completed, short_close_operation=short_close)


def row(idx=1, planned=100):
    return frappe._dict(idx=idx, planned_qty=planned)


class TestProducedQtyChanges(FrappeTestCase):
    def test_submit_first_operation_in_progress(self):
        op_values, ps_values = get_produced_qty_changes(card(40), "Submit", sheet(), row(), 40)
        self.assertEqual(op_values, {"completed_qty": 40, "status": "In Progress"})
        self.assertEqual(ps_values, {"status": "In Progress", "produced_qty": 40})

    def test_submit_first_operation_completes_sheet(self):
        op_values, ps_values = get_produced_qty_changes(
            card(60), "Submit", sheet("In Progress", produced=40), row(), 100
        )
        self.assertEqual(op_values, {"completed_qty": 100, "status": "Completed"})
        self.assertEqual(ps_values, {"produced_qty": 100, "status": "Completed"})

    def test_submit_short_close(self):
        op_values, ps_values = get_produced_qty_changes(
            card(30, short_close=1), "Submit", sheet("In Progress", produced=40), row(), 70
        )
        self.assertEqual(op_values, {"completed_qty": 70, "status": "Completed"})
        self.assertEqual(
            ps_values, {"produced_qty": 100, "short_closed_qty": 30, "status": "Short Closed"}
        )

    def test_submit_later_operation_writes_only_the_operation(self):
        op_values, ps_values = get_produced_qty_changes(card(40), "Submit", sheet("In Progress"), row(idx=2), 40)
        self.assertEqual(op_values, {"completed_qty": 40, "status": "In Progress"})
        self.assertEqual(ps_values, {})

    def test_cancel_first_operation(self):
        op_values, ps_values = get_produced_qty_changes(
            card(40), "Cancel", sheet("In Progress", produced=40), row(), 0
        )
        self.assertEqual(op_values, {"completed_qty": 0, "status": "In Progress"})
        self.assertEqual(ps_values, {"produced_qty": 0})

    def test_cancel_short_closed(self):
        op_values, ps_values = get_produced_qty_changes(
            card(30, short_close=1), "Cancel", sheet("Short Closed", produced=100, short_closed=30), row(), 40
        )
        self.assertEqual(op_values, {"completed_qty": 40, "status": "In Progress"})
        self.assertEqual(ps_values, {"produced_qty": 40, "short_closed_qty": 0})


def ps_op(operation="Grinding", status="Pending", completed_qty=0, planned_qty=10):
    return frappe._dict(
        operation=operation, status=status, completed_qty=completed_qty, planned_qty=planned_qty
    )


def totals(comp_qty=None, sc_op=None):
    return frappe._dict(comp_qty=comp_qty, sc_op=sc_op)


class TestGetOperationValues(FrappeTestCase):
    TEMPLATE = {"Grinding"}

    def values(self, opd, jc, ps_status="In Progress"):
        from rigpl_erpnext.manufacturing_rigpl.utils.process_sheet_utils import get_operation_values

        return get_operation_values(opd, jc, ps_status, self.TEMPLATE)

    def test_no_job_cards_is_pending(self):
        self.assertEqual(self.values(ps_op(status=None), None), (0, "Pending"))

    def test_partly_done_is_in_progress(self):
        self.assertEqual(self.values(ps_op(), totals(4)), (4, "In Progress"))

    def test_fully_done_is_completed(self):
        self.assertEqual(self.values(ps_op(), totals(10)), (10, "Completed"))

    def test_short_closed(self):
        self.assertEqual(self.values(ps_op(), totals(4, 1)), (4, "Short Closed"))
        self.assertEqual(self.values(ps_op(), totals(0, 1)), (0, "Short Closed"))

    def test_stopped_sheet(self):
        self.assertEqual(self.values(ps_op(), totals(4), "Stopped"), (4, "Stopped"))
        self.assertEqual(self.values(ps_op(), None, "Stopped"), (0, "Stopped"))

    def test_operation_not_in_template_is_obsolete(self):
        self.assertEqual(self.values(ps_op("Coating"), None), (0, "Obsolete"))
        self.assertEqual(self.values(ps_op("Coating"), totals(4)), (4, "Obsolete"))
        self.assertEqual(self.values(ps_op("Coating"), totals(10)), (10, "Completed"))


class TestBatchQtyHelpers(FrappeTestCase):
    MULTIPLIERS = [
        {"multiplier": 5, "value": 1000},
        {"multiplier": 2.5, "value": 2000},
        {"multiplier": 2, "value": 2500},
    ]

    def test_calculated_rol_uses_the_last_band_that_fits(self):
        from rigpl_erpnext.utils.stock_utils import get_calculated_rol

        # The last band that fits wins, so the 5x and 2.5x bands are never used (old behavior)
        self.assertEqual(get_calculated_rol(10, 50, self.MULTIPLIERS), 20)
        self.assertEqual(get_calculated_rol(10, 220, self.MULTIPLIERS), 20)
        self.assertEqual(get_calculated_rol(10, 300, self.MULTIPLIERS), 10)

    def test_so_lines_filter_by_so_detail(self):
        from rigpl_erpnext.utils.sales_utils import get_so_date_value

        lines = [frappe._dict(name="SO1", so_detail="A"), frappe._dict(name="SO2", so_detail="B")]
        rows = get_so_date_value("IT", prd_qty=5, short_qty=2, so_detail="B", so_lines=lines)
        self.assertEqual([(r.name, r.prd_qty, r.shortage) for r in rows], [("SO2", 5, 2)])
        self.assertEqual(len(get_so_date_value("IT", 5, so_lines=lines)), 2)
