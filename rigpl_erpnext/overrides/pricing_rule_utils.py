"""
Backport of ERPNext v14 "Has Priority" pricing rule lookup to ERPNext v13.

In v13, get_pricing_rules stops after the Item Code stage when any Item Code
rule matches, even if that rule later fails its min/max qty or amount check.
MOV rules on Item Templates (priority 19) therefore hide the customer's Item
Group rule on orders below the MOV. Upstream fixed this in v14 with commit
97fdda8a7c ("fix: priority not working for multiple pricing rules", #41516):
when the top rule has has_priority, the lookup continues to the next stage and
the normal qty/amount filter and priority selection pick one rule.

REMOVE THIS MODULE AT THE v14 UPGRADE. See patches/v13/NOTES_v14_upgrade.md.
"""

import erpnext
import frappe
from erpnext.accounts.doctype.pricing_rule import utils


def apply_overrides(**kwargs):
    """Replace utils.get_pricing_rules on ERPNext v13 only. Safe to call on every request/job."""
    if utils.get_pricing_rules is get_pricing_rules:
        return
    if not erpnext.__version__.startswith("13."):
        frappe.logger("rigpl_erpnext").warning(
            f"Pricing rule override skipped: ERPNext {erpnext.__version__} is not v13. "
            "Remove rigpl_erpnext.overrides.pricing_rule_utils."
        )
        return
    # get_pricing_rule_for_item imports get_pricing_rules inside the function, so the
    # module attribute is looked up on every call.
    utils.get_pricing_rules = get_pricing_rules


def get_pricing_rules(args, doc=None):
    """Copy of ERPNext v13.55.2 utils.get_pricing_rules with the v14 has_priority check."""
    pricing_rules = []
    values = {}

    if not frappe.db.exists("Pricing Rule", {"disable": 0, args.transaction_type: 1}):
        return

    for apply_on in ["Item Code", "Item Group", "Brand"]:
        pricing_rules.extend(utils._get_pricing_rules(apply_on, args, values))
        if pricing_rules and pricing_rules[0].has_priority:
            continue

        if pricing_rules and not utils.apply_multiple_pricing_rules(pricing_rules):
            break

    rules = []

    pricing_rules = utils.filter_pricing_rule_based_on_condition(pricing_rules, doc)

    if not pricing_rules:
        return []

    if utils.apply_multiple_pricing_rules(pricing_rules):
        pricing_rules = utils.sorted_by_priority(pricing_rules, args, doc)
        for pricing_rule in pricing_rules:
            if isinstance(pricing_rule, list):
                rules.extend(pricing_rule)
            else:
                rules.append(pricing_rule)
    else:
        pricing_rule = utils.filter_pricing_rules(args, pricing_rules, doc)
        if pricing_rule:
            rules.append(pricing_rule)

    return rules
