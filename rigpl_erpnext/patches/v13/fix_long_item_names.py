import frappe
from frappe.query_builder import Case, CustomFunction, DocType

# CHAR_LENGTH, not LENGTH: LENGTH counts bytes and miscounts multi-byte names.
CharLength = CustomFunction("CHAR_LENGTH", ["text"])


def execute():
    """
    Runs before migrate. Finds Items whose item_name is longer than the field length
    (140, or the length set with Customize Form) and replaces it with item_code (or
    name if item_code is also too long), so the schema sync does not fail.
    """
    max_len = frappe.get_meta("Item").get_field("item_name").length or 140
    item = DocType("Item")
    rows = (
        frappe.qb.from_(item)
        .select(item.name)
        .where(CharLength(item.item_name) > max_len)
    ).run(as_list=True)
    long_items = [row[0] for row in rows]
    if not long_items:
        return

    (
        frappe.qb.update(item)
        .set(
            item.item_name,
            Case().when(CharLength(item.item_code) <= max_len, item.item_code).else_(item.name),
        )
        .where(CharLength(item.item_name) > max_len)
    ).run()
    print(f"Shortened item_name for {len(long_items)} Items: {', '.join(long_items)}")
