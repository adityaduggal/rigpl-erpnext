import frappe


def execute():
    """
    #168: the carrier codes that the adapters know go into Shipping Status Map. A row that
    exists is not changed, so a status set by a user stays. The rows are in
    shipping/seed_rules.py, so a provider is seeded before its adapter exists.
    """
    frappe.reload_doc("rigpl_erpnext", "doctype", "shipping_status_map")
    from rigpl_erpnext.rigpl_erpnext.shipping.seed_rules import SEED_RULES
    from rigpl_erpnext.rigpl_erpnext.shipping.status_map import insert_rules

    for name, rules in SEED_RULES.items():
        added = insert_rules(name, rules)
        print(f"Shipping Status Map: {added} rows added for {name}")
