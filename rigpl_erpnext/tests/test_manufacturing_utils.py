
import frappe
from frappe.tests.utils import FrappeTestCase, change_settings

from rigpl_erpnext.manufacturing_rigpl.utils.job_card_utils import match_existing_job_cards
from rigpl_erpnext.manufacturing_rigpl.utils.manufacturing_utils import (
    FG_RULES_CACHE_KEY,
    age_adjusted_rate,
    clear_fg_rules_cache,
    find_item_quantities,
    get_best_rm_bypass,
    get_candidate_templates,
    get_fg_restriction_rules,
    get_items_for_rules,
    get_produced_qty_changes,
    get_qty_for_prod,
    get_qty_for_prod_map,
    get_rm_age_discount_settings,
    get_rm_rule_errors,
    get_rule_failures,
    get_template_usage,
    match_bom_templates,
    match_bom_templates_bulk,
    prepare_fg_rules,
    rank_rm_rows,
    round_up_qty,
    rule_passes,
    set_wip_row_quantities,
    split_allowed_values,
)
from rigpl_erpnext.tests.test_check_update_bin_values import insert_bin, insert_process_sheet, insert_stock_item
from rigpl_erpnext.tests.test_variant_table import insert_item
from rigpl_erpnext.utils.guide_utils import get_user_guide
from rohit_common.utils.query_guard import assert_max_queries


def att(attribute, value, numeric=0):
    return frappe._dict(attribute=attribute, attribute_value=value, numeric_values=numeric)


def rule(attribute, allowed="", numeric=0, formula=""):
    return frappe._dict(attribute=attribute, allowed_values=allowed, is_numeric=numeric, rule=formula)


ITEM = [att("Base Material", "HSS"), att("Tool Type", "Drill"), att("d1_mm", "6", numeric=1)]


def match(rules, item, priority=None, usage=None):
    return match_bom_templates(prepare_fg_rules(rules, priority), item, usage)


class TestMatchBomTemplates(FrappeTestCase):
    def test_text_rules(self):
        rules = {
            "BT1": [rule("Base Material", "HSS"), rule("Tool Type", "Drill")],
            "BT2": [rule("Base Material", "HSS"), rule("Tool Type", "Reamer")],
            "BT3": [rule("Base Material", "Carbide")],
        }
        self.assertEqual(match(rules, ITEM), ["BT1"])

    def test_missing_attribute_does_not_match(self):
        rules = {"BT1": [rule("Base Material", "HSS"), rule("Series", "C3HS")]}
        self.assertEqual(match(rules, ITEM), [])

    def test_template_without_rules_matches_all(self):
        self.assertEqual(match({"BT1": []}, ITEM), ["BT1"])
        self.assertEqual(match({"BT1": []}, []), ["BT1"])

    def test_numeric_rule(self):
        rules = {
            "BT1": [rule("Base Material", "HSS"), rule("d1_mm", numeric=1, formula="fg_d1_mm >= 5")],
            "BT2": [rule("Base Material", "HSS"), rule("d1_mm", numeric=1, formula="fg_d1_mm > 10")],
        }
        self.assertEqual(match(rules, ITEM), ["BT1"])

    def test_multi_value_rule(self):
        rules = {
            "BT1": [rule("Base Material", "Carbide\nHSS"), rule("Tool Type", "Reamer\n Drill ")],
            "BT2": [rule("Base Material", "Carbide\nCobalt")],
        }
        self.assertEqual(match(rules, ITEM), ["BT1"])
        self.assertEqual(split_allowed_values(" A\n\nB \n"), {"A", "B"})

    def test_sort_priority_then_item_usage_then_name(self):
        rules = {name: [rule("Base Material", "HSS")] for name in ("BT4", "BT3", "BT2", "BT1")}
        self.assertEqual(match(rules, ITEM), ["BT1", "BT2", "BT3", "BT4"])
        self.assertEqual(
            match(rules, ITEM, priority={"BT4": 5}, usage={"BT3": 9, "BT2": 2, "BT4": 1}),
            ["BT4", "BT3", "BT2", "BT1"],
        )

    def test_index_checks_only_the_item_key(self):
        rules = {
            "BT1": [rule("Base Material", "HSS"), rule("Tool Type", "Drill")],
            "BT2": [rule("Base Material", "HSS"), rule("Tool Type", "Reamer\nTap")],
            "BT3": [rule("Tool Type", "Drill")],
            "BT4": [rule("Base Material", "Carbide")],
            "BT5": [],
        }
        self.assertEqual(get_candidate_templates(prepare_fg_rules(rules), ITEM), {"BT1", "BT3", "BT5"})


class TestRuleCheck(FrappeTestCase):
    def test_rule_passes(self):
        values = {"rm_d1_mm": 6.0, "fg_d1_mm": 4.5}
        self.assertTrue(rule_passes("rm_d1_mm == fg_d1_mm + 1.5", values))
        self.assertTrue(rule_passes("rm_d1_mm >= ceiling(fg_d1_mm)  and  rm_d1_mm <= 6", values))
        self.assertFalse(rule_passes("rm_d1_mm < CEILING(fg_d1_mm)", values))

    def test_missing_value_does_not_pass(self):
        self.assertFalse(rule_passes("rm_l1_mm > 5", {"rm_d1_mm": 6.0}))

    def test_decimal_values_on_the_limit_pass(self):
        # In float 2.2 + 0.2 is 2.4000000000000004, which is more than 2.4 (PS2701163)
        values = {"rm_d1_mm": 2.4, "fg_d1_mm": 2.2}
        self.assertTrue(rule_passes("rm_d1_mm <= (fg_d1_mm + 2) and rm_d1_mm >= (fg_d1_mm + 0.2)", values))
        self.assertTrue(rule_passes("rm_d1_mm == fg_d1_mm + .2", values))
        self.assertFalse(rule_passes("rm_d1_mm > fg_d1_mm + 0.2", values))

    def test_rule_failures_of_one_item(self):
        restrictions = [
            rule("Base Material", "HSS\nCarbide"), rule("Tool Type", "No"),
            rule("d1_mm", numeric=1, formula="rm_d1_mm >= fg_d1_mm && rm_d1_mm <= fg_d1_mm + 2"),
        ]
        known = {"fg_d1_mm": 6.0}
        self.assertEqual(get_rule_failures(restrictions, known, "rm",
            [att("Base Material", "HSS"), att("d1_mm", "7", 1)]), [])
        self.assertEqual(get_rule_failures(restrictions, known, "rm",
            [att("Base Material", "Cobalt"), att("d1_mm", "9", 1)]),
            ["Base Material = Cobalt, allowed: Carbide, HSS", "rm_d1_mm >= fg_d1_mm && rm_d1_mm <= fg_d1_mm + 2"])
        self.assertEqual(get_rule_failures(restrictions, known, "rm", [att("d1_mm", "7", 1)]),
            ["Base Material = not set, allowed: Carbide, HSS"])


class TestRankRmRows(FrappeTestCase):
    def test_lowest_cost_first_and_no_rate_last(self):
        rows = [
            frappe._dict(item_code="RM-A", calculated_qty=866),
            frappe._dict(item_code="RM-B", calculated_qty=2600),
            frappe._dict(item_code="RM-C", calculated_qty=100),
            frappe._dict(item_code="RM-D", calculated_qty=2600),
        ]
        rank_rm_rows(rows, {"RM-A": 2960, "RM-B": 200, "RM-D": 300}, settings=(100, 5))
        self.assertEqual([d.item_code for d in rows], ["RM-B", "RM-D", "RM-A", "RM-C"])
        self.assertEqual([d.idx for d in rows], [1, 2, 3, 4])
        self.assertEqual(rows[0].rm_cost, 520000)
        self.assertEqual(rows[0].adjusted_rm_cost, 520000)
        self.assertEqual(rows[3].valuation_rate, 0)

    def test_old_stock_ranks_by_its_discount(self):
        rows = [
            frappe._dict(item_code="RM-NEW", calculated_qty=10, average_stock_age=30),
            frappe._dict(item_code="RM-OLD", calculated_qty=10, average_stock_age=1000),
            frappe._dict(item_code="RM-OLD-DEAR", calculated_qty=10, average_stock_age=1000),
        ]
        rank_rm_rows(rows, {"RM-NEW": 100, "RM-OLD": 150, "RM-OLD-DEAR": 250}, settings=(100, 5))
        # 1000 days = 10 steps of 5%: 150 -> 75 is first, 250 -> 125 is after the new 100
        self.assertEqual([d.item_code for d in rows], ["RM-OLD", "RM-NEW", "RM-OLD-DEAR"])
        self.assertEqual(rows[0].age_adjusted_rate, 75)
        self.assertEqual(rows[0].rm_cost, 1500)
        self.assertEqual(rows[0].adjusted_rm_cost, 750)


class TestAgeAdjustedRate(FrappeTestCase):
    def test_full_steps_only_and_never_below_zero(self):
        for age, rate in ((0, 100), (99, 100), (100, 95), (1000, 50), (1999, 5), (2500, 0)):
            self.assertAlmostEqual(age_adjusted_rate(100, age, 100, 5), rate, msg=age)

    def test_no_step_days_gives_no_discount(self):
        self.assertEqual(age_adjusted_rate(100, 1000, 0, 5), 100)

    @change_settings("RIGPL Settings", {"rm_age_step_days": 50, "rm_age_step_discount": 10})
    def test_settings(self):
        self.assertEqual(get_rm_age_discount_settings(), (50, 10))

    @change_settings("RIGPL Settings", {"rm_age_step_days": 0})
    def test_empty_step_days_uses_the_default(self):
        self.assertEqual(get_rm_age_discount_settings()[0], 100)


class TestBestRmBypass(FrappeTestCase):
    def ranked(self):
        return [
            frappe._dict(item_code="RM-1", valuation_rate=10, adjusted_rm_cost=100),
            frappe._dict(item_code="RM-2", valuation_rate=10, adjusted_rm_cost=100),
            frappe._dict(item_code="RM-3", valuation_rate=10, adjusted_rm_cost=150),
            frappe._dict(item_code="RM-4", valuation_rate=0, adjusted_rm_cost=0),
        ]

    def test_rank_one_or_same_cost_is_not_a_bypass(self):
        ranked = self.ranked()
        self.assertIsNone(get_best_rm_bypass([ranked[0]], ranked))
        self.assertIsNone(get_best_rm_bypass([ranked[1]], ranked))

    def test_higher_cost_or_no_rate_is_a_bypass(self):
        ranked = self.ranked()
        self.assertEqual(get_best_rm_bypass([ranked[2]], ranked), (ranked[0], ranked[2]))
        self.assertEqual(get_best_rm_bypass([ranked[3]], ranked), (ranked[0], ranked[3]))

    def test_no_rate_for_rank_one_is_not_checked(self):
        ranked = [frappe._dict(item_code="RM-4", valuation_rate=0, adjusted_rm_cost=0)]
        self.assertIsNone(get_best_rm_bypass([frappe._dict(item_code="RM-X", valuation_rate=5)], ranked))


class TestRoundUpQty(FrappeTestCase):
    def test_round_up(self):
        self.assertEqual(round_up_qty(25.7), 26)
        self.assertEqual(round_up_qty(26.06158079999999), 27)
        self.assertEqual(round_up_qty(26.0000001), 26)
        self.assertEqual(round_up_qty(26), 26)


class TestUserGuide(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")

    def test_guides(self):
        self.assertIn("<h1", get_user_guide("bom_templates"))
        self.assertIn("<h1", get_user_guide("process_sheet"))
        self.assertRaises(frappe.ValidationError, get_user_guide, "../../hooks")
        frappe.set_user("Guest")
        self.assertRaises(frappe.PermissionError, get_user_guide, "process_sheet")


class TestFgRulesCache(FrappeTestCase):
    def tearDown(self):
        clear_fg_rules_cache()

    def test_cache_is_used_and_cleared(self):
        clear_fg_rules_cache()
        get_fg_restriction_rules()
        self.assertIsNotNone(frappe.cache().get_value(FG_RULES_CACHE_KEY))
        with assert_max_queries(0, test_case=self):
            get_fg_restriction_rules()
        clear_fg_rules_cache()
        self.assertIsNone(frappe.cache().get_value(FG_RULES_CACHE_KEY))

    def test_disabled_template_is_not_read(self):
        disabled = frappe.get_all("BOM Template RIGPL", filters={"disabled": 1}, pluck="name")
        if not disabled:
            self.skipTest("No disabled BOM Template on this site")
        clear_fg_rules_cache()
        self.assertFalse(set(disabled) & set(get_fg_restriction_rules()["rules"]))


class TestMatchBomTemplatesBulk(FrappeTestCase):
    def test_bulk_is_same_as_single_with_fixed_queries(self):
        items = frappe.get_all(
            "Item",
            filters={"disabled": 0, "include_item_in_manufacturing": 1, "variant_of": ("is", "set")},
            pluck="name",
            limit=50,
        )
        if not items:
            self.skipTest("No manufacturing variants on this site")
        match_bom_templates_bulk(items[:1])
        # 1 attribute query and 1 usage query for the chunk; the rules come from the cache
        with assert_max_queries(2, test_case=self):
            bulk = match_bom_templates_bulk(items)
        prepared = get_fg_restriction_rules()
        usage = get_template_usage(items)
        for item in items:
            single = match_bom_templates(prepared, frappe.get_all(
                "Item Variant Attribute",
                filters={"parent": item, "parenttype": "Item"},
                fields=["attribute", "attribute_value", "numeric_values"],
                order_by="idx",
            ), usage.get(item))
            self.assertEqual(bulk[item], single, item)


TEST_BM = "_Test RIGPL BM"


class TestItemsForRules(FrappeTestCase):
    def setUp(self):
        for name, d1, l1 in (("_Test RIGPL RM 6x50", "6", "50"), ("_Test RIGPL RM 8x50", "8", "50"),
                             ("_Test RIGPL RM 6x20", "6", "20")):
            insert_item(name, variant_of="_Test RIGPL RM", attributes=[
                ("Base Material", TEST_BM), ("d1_mm", d1), ("l1_mm", l1)])
            frappe.db.set_value("Item", name, "end_of_life", "2099-12-31")
        insert_item("_Test RIGPL RM other", variant_of="_Test RIGPL RM", attributes=[
            ("Base Material", "_Test RIGPL other"), ("d1_mm", "6"), ("l1_mm", "50")])
        frappe.db.set_value("Item", "_Test RIGPL RM other", "end_of_life", "2099-12-31")

    def tearDown(self):
        frappe.db.rollback()

    def test_text_and_numeric_rules(self):
        restrictions = [
            rule("Base Material", TEST_BM + "2\n" + TEST_BM),
            rule("d1_mm", numeric=1, formula="rm_d1_mm == fg_d2_mm || rm_d1_mm == fg_d2_mm + 2"),
            rule("l1_mm", numeric=1, formula="rm_l1_mm >= fg_l2_mm"),
        ]
        known = {"fg": [att("d2_mm", "6", 1), att("l2_mm", "40", 1)]}
        names = [d.name for d in get_items_for_rules(restrictions, known, "rm", allow_zero_rol=1)]
        self.assertEqual(names, ["_Test RIGPL RM 6x50", "_Test RIGPL RM 8x50"])

    def test_rm_rows_that_fail_the_rules(self):
        insert_item("_Test RIGPL FG 6x40", variant_of="_Test RIGPL FG", attributes=[("d2_mm", "6"), ("l2_mm", "40")])
        bt_doc = frappe._dict(name="_Test RIGPL BT", rm_restrictions=[
            rule("Base Material", TEST_BM),
            rule("d1_mm", numeric=1, formula="rm_d1_mm == fg_d2_mm"),
            rule("l1_mm", numeric=1, formula="rm_l1_mm >= fg_l2_mm"),
        ])
        rows = [frappe._dict(idx=1, item_code="_Test RIGPL RM 6x50")]
        get_rm_rule_errors(bt_doc, "_Test RIGPL FG 6x40", None, rows)  # loads the meta into the cache
        with assert_max_queries(3, test_case=self):
            self.assertEqual(get_rm_rule_errors(bt_doc, "_Test RIGPL FG 6x40", None, rows), [])

        rows += [frappe._dict(idx=2, item_code="_Test RIGPL RM 8x50"), frappe._dict(idx=3, item_code="_Test RIGPL RM 6x20"),
            frappe._dict(idx=4, item_code="_Test RIGPL RM other")]
        with assert_max_queries(3, test_case=self):
            errors = get_rm_rule_errors(bt_doc, "_Test RIGPL FG 6x40", None, rows)
        self.assertEqual([(row.idx, failures) for row, failures in errors], [
            (2, ["rm_d1_mm == fg_d2_mm"]),
            (3, ["rm_l1_mm >= fg_l2_mm"]),
            (4, ["Base Material = _Test RIGPL other, allowed: " + TEST_BM]),
        ])

    def test_no_value_is_not_a_filter_and_rol_filter(self):
        restrictions = [rule("Base Material", TEST_BM), rule("Tool Type", "No")]
        self.assertEqual(len(get_items_for_rules(restrictions, {}, "rm", allow_zero_rol=1)), 3)
        self.assertEqual(get_items_for_rules(restrictions, {}, "rm", allow_zero_rol=0), [])


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

    def test_open_job_cards_for_item_with_quote_in_name(self):
        from rigpl_erpnext.manufacturing_rigpl.utils.job_card_utils import get_open_job_cards_for_item

        self.assertEqual(get_open_job_cards_for_item("No Such Item's Name"), [])


QTY_ITEM = "_Test RIGPL O'Brien RM"
QTY_WH = "_Test RIGPL O'Brien RM WH"
SUBCON_WH = "_Test RIGPL O'Brien Subcon WH"


class TestItemQuantityQueries(FrappeTestCase):
    def setUp(self):
        insert_stock_item(QTY_ITEM)
        for name, subcon in ((QTY_WH, 0), (SUBCON_WH, 1)):
            frappe.get_doc(doctype="Warehouse", name=name, warehouse_name=name, short_code=name[-4:],
                is_subcontracting_warehouse=subcon).db_insert()

    def tearDown(self):
        frappe.db.rollback()

    def test_find_item_quantities_adds_subcon_stock_for_name_rows(self):
        insert_bin(QTY_ITEM, QTY_WH, actual_qty=10, reserved_qty=2, ordered_qty=3)
        insert_bin(QTY_ITEM, SUBCON_WH, actual_qty=4)

        rows = find_item_quantities([{"name": QTY_ITEM}])

        self.assertEqual(sorted((r.warehouse, r.actual_qty) for r in rows), [(QTY_WH, 10), (SUBCON_WH, 4)])
        self.assertEqual({(r.on_so, r.on_po) for r in rows}, {(2, 7)})

    def test_wip_totals_are_not_added_per_bin(self):
        wip = frappe._dict(item_code=QTY_ITEM)
        qty_rows = [frappe._dict(item_code=QTY_ITEM, stock_uom="Nos", actual_qty=qty, on_so=2, on_po=3,
            prd_qty=1, planned=4) for qty in (10, 4)]

        set_wip_row_quantities(wip, qty_rows)

        self.assertEqual((wip.qty_available, wip.current_projected_qty, wip.projected_qty), (14, 11, 18))

    def test_qty_for_prod_of_open_process_sheets(self):
        insert_process_sheet("_Test RIGPL O'Brien FG", QTY_WH, 1, rm_item=QTY_ITEM, rm_warehouse=QTY_WH, rm_qty=5)
        insert_process_sheet("_Test RIGPL O'Brien FG", QTY_WH, 1, rm_item=QTY_ITEM, rm_warehouse=SUBCON_WH,
            rm_qty=2)

        self.assertEqual(get_qty_for_prod(QTY_ITEM, QTY_WH, "rm_consumed"), 5)
        with assert_max_queries(1, test_case=self):
            qtys = get_qty_for_prod_map([(QTY_ITEM, QTY_WH), (QTY_ITEM, SUBCON_WH)], "rm_consumed")
        self.assertEqual(qtys, {(QTY_ITEM, QTY_WH): 5, (QTY_ITEM, SUBCON_WH): 2})
