import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

WAREHOUSE_RULES = {
    "Dead Stock - RIGPL": ("Percent of Rate", 25),
    "REJ-DEL20A - RIGPL": ("Fixed Rate", 1),
}


def execute():
    """
    Adds the Manual Rate check (permlevel 1) to Stock Reconciliation Item and the valuation
    rule to Warehouse, and moves the hard-coded Dead Stock and Rejected warehouse rates
    into the Warehouse rule (#155).
    """
    create_custom_fields(
        {
            "Stock Reconciliation Item": [
                {
                    "fieldname": "manual_valuation_rate",
                    "fieldtype": "Check",
                    "label": "Manual Rate",
                    "insert_after": "valuation_rate",
                    "permlevel": 1,
                    "default": "0",
                    "description": "If set, the Valuation Rate is not changed on save",
                },
            ],
            "Warehouse": [
                {
                    "fieldname": "valuation_rule",
                    "fieldtype": "Select",
                    "label": "Valuation Rule",
                    "options": "\nPercent of Rate\nFixed Rate",
                    "insert_after": "parent_warehouse",
                    "description": "Rate used in Stock Reconciliation for this warehouse",
                },
                {
                    "fieldname": "valuation_rule_value",
                    "fieldtype": "Float",
                    "label": "Valuation Rule Value",
                    "insert_after": "valuation_rule",
                    "depends_on": "valuation_rule",
                },
            ],
        }
    )
    for role in ("System Manager", "Stock Manager"):
        add_permission("Stock Reconciliation", role, 1)
        update_permission_property("Stock Reconciliation", role, 1, "write", 1)
    for warehouse, (rule, value) in WAREHOUSE_RULES.items():
        if frappe.db.exists("Warehouse", warehouse):
            frappe.db.set_value(
                "Warehouse", warehouse, {"valuation_rule": rule, "valuation_rule_value": value},
                update_modified=False,
            )
