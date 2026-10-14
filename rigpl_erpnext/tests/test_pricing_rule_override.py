import unittest
from unittest.mock import patch

import frappe
from erpnext.accounts.doctype.pricing_rule import utils

from rigpl_erpnext.overrides import pricing_rule_utils

MOV_RULE = {"name": "MOV", "priority": "19", "min_amt": 100000, "apply_on": "Item Code"}
GROUP_RULE = {"name": "GROUP", "priority": "2", "min_amt": 0, "apply_on": "Item Group"}


def make_rule(rule, has_priority):
    return frappe._dict(rule, has_priority=has_priority, apply_multiple_pricing_rules=0, discount_percentage=0)


def pick_by_amount(args, pricing_rules, doc=None):
    """Same order as v13 filter_pricing_rules: amount filter, then highest priority."""
    amount = args.price_list_rate * args.qty
    rules = [r for r in pricing_rules if amount >= r.min_amt]
    return max(rules, key=lambda r: int(r.priority)) if rules else None


class TestPricingRuleOverride(unittest.TestCase):
    def get_winner(self, qty, has_priority=1):
        stages = {
            "Item Code": [make_rule(MOV_RULE, has_priority)],
            "Item Group": [make_rule(GROUP_RULE, has_priority)],
            "Brand": [],
        }
        args = frappe._dict(transaction_type="selling", price_list_rate=1000, qty=qty)
        with patch.object(utils, "_get_pricing_rules", lambda apply_on, a, v: list(stages[apply_on])), patch.object(
            utils, "filter_pricing_rules", pick_by_amount
        ), patch.object(frappe.db, "exists", return_value=True):
            rules = pricing_rule_utils.get_pricing_rules(args)
        return rules[0].name if rules else None

    def test_below_mov_falls_through_to_item_group(self):
        self.assertEqual(self.get_winner(qty=1), "GROUP")

    def test_mov_met_wins(self):
        self.assertEqual(self.get_winner(qty=100), "MOV")

    def test_without_has_priority_keeps_v13_stop(self):
        self.assertIsNone(self.get_winner(qty=1, has_priority=0))

    def test_override_skipped_on_other_erpnext_version(self):
        original = utils.get_pricing_rules
        with patch.object(pricing_rule_utils.erpnext, "__version__", "14.0.0"):
            pricing_rule_utils.apply_overrides()
            self.assertIs(utils.get_pricing_rules, original)
