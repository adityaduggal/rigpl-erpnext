import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.query_builder import DocType
from frappe.query_builder.functions import IfNull


def execute():
    """
    Adds Pricing Rule.has_priority, used by overrides.pricing_rule_utils. It has the
    same fieldname as the v14 standard field, so the values carry over at the v14
    upgrade. Ticks it where priority is set, as v14 patch
    enable_set_priority_for_pricing_rules does.
    """
    create_custom_field(
        "Pricing Rule",
        {
            "fieldname": "has_priority",
            "fieldtype": "Check",
            "label": "Has Priority",
            "insert_after": "priority",
            "default": "0",
            "description": "v13 backport: if set, lower Item Group/Brand rules are also checked",
        },
    )
    pricing_rule = DocType("Pricing Rule")
    (
        frappe.qb.update(pricing_rule)
        .set(pricing_rule.has_priority, 1)
        .where(IfNull(pricing_rule.priority, "") != "")
        .where(pricing_rule.has_priority == 0)
    ).run()
