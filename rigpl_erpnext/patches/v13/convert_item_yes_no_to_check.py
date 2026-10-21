import frappe

FIELDS = ("pl_item", "stock_maintained")


def execute():
    """
    Item `pl_item` and `stock_maintained` change from a Yes/No Select to a Check (#106).
    "Yes" becomes 1. "No" and empty become 0. Migrate runs the patches before it syncs the
    custom fields, so this patch converts the values while the column is still text, then
    changes the Custom Field and the column itself. Idempotent: a field that is a Check
    already is skipped.
    """
    item = frappe.qb.DocType("Item")
    changed = False
    for field in FIELDS:
        custom_field = frappe.db.get_value(
            "Custom Field", {"dt": "Item", "fieldname": field}, ["name", "fieldtype"], as_dict=True
        )
        if not custom_field or custom_field.fieldtype == "Check":
            continue

        yes_before = frappe.db.count("Item", {field: "Yes"})
        frappe.qb.update(item).set(item[field], "1").where(item[field] == "Yes").run()
        frappe.qb.update(item).set(item[field], "0").where(
            item[field].isnull() | (item[field] != "1")
        ).run()
        frappe.db.set_value(
            "Custom Field", custom_field.name, {"fieldtype": "Check", "options": None, "default": "0"}
        )
        changed = True
        print(f"Item {field}: {yes_before} Yes became 1, the other Items became 0.")

    if not changed:
        return

    frappe.clear_cache(doctype="Item")
    frappe.db.updatedb("Item")  # the columns become int(1)
    for field in FIELDS:
        yes_after = frappe.db.count("Item", {field: 1})
        print(f"Item {field}: {yes_after} Items are 1 after the change.")

