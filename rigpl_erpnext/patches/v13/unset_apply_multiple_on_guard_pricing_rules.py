import frappe

from rigpl_erpnext.utils.batch_write_utils import bulk_set_fields


def execute():
    """
    Guard rules give 0% on an Item Group for all customers, so users cannot type their
    own discount when a customer has no rule. In v12 their "Apply Multiple Pricing Rules"
    made all matched rules apply together. In v13 it makes only the flagged rules apply,
    so the customer's own Item Group rule is dropped and the guard's 0% wins. Without the
    flag, v13 selects the matched rule with the highest priority. The guards stay enabled
    and keep their priority.
    """
    guards = frappe.get_all(
        "Pricing Rule",
        filters={
            "disable": 0,
            "selling": 1,
            "apply_on": "Item Group",
            "apply_multiple_pricing_rules": 1,
            "rate_or_discount": "Discount Percentage",
            "discount_percentage": 0,
            "margin_rate_or_amount": 0,
            "customer": ("is", "not set"),
            "customer_group": ("is", "not set"),
            "territory": ("is", "not set"),
        },
        pluck="name",
    )
    field = "apply_multiple_pricing_rules"
    bulk_set_fields(
        "Pricing Rule",
        {name: {field: 0} for name in guards},
        {name: {field: 1} for name in guards},
        add_versions=False,
        update_modified=True,
    )
    for name in guards:
        print(f"Pricing Rule {name}: Apply Multiple Pricing Rules 1 -> 0")
