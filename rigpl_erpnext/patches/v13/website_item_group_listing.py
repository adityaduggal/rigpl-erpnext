import frappe


def execute():
    """
    Category pages list templates, not variants, with ERPNext's own settings (#103):
    - E Commerce Settings Hide Variants on. Attribute Filters off, because ERPNext turns Hide
      Variants off while they are on, and a template has no attribute values. The filter
      rows stay, so they can be turned on again.
    - Include Descendants on each shown parent Item Group, so it lists the templates of its
      sub-categories and is not empty.
    Idempotent.
    """
    settings = "E Commerce Settings"
    if not frappe.db.get_single_value(settings, "hide_variants"):
        frappe.db.set_single_value(settings, "hide_variants", 1)
        print("E Commerce Settings: Hide Variants is on.")
    if frappe.db.get_single_value(settings, "enable_attribute_filters"):
        frappe.db.set_single_value(settings, "enable_attribute_filters", 0)
        print("E Commerce Settings: Attribute Filters are off.")

    item_group = frappe.qb.DocType("Item Group")
    condition = (
        (item_group.show_in_website == 1) & (item_group.is_group == 1) & (item_group.include_descendants == 0)
    )
    count = len(frappe.qb.from_(item_group).select(item_group.name).where(condition).run())
    if count:
        frappe.qb.update(item_group).set(item_group.include_descendants, 1).where(condition).run()
        print(f"Item Groups: Include Descendants is on for {count} shown parent groups.")

    frappe.clear_cache(doctype=settings)
    frappe.clear_cache(doctype="Item Group")
