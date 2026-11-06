import frappe
from frappe.query_builder import Case, CustomFunction, DocType

# CHAR_LENGTH, not LENGTH: LENGTH counts bytes and miscounts multi-byte names.
CharLength = CustomFunction("CHAR_LENGTH", ["text"])

WEBSITE_ITEM = "Website Item"
WEBSITE_ITEM_NAME_FIELDS = ("item_name", "web_item_name")


def execute():
    shorten_long_item_names()
    add_website_item_length_setters()


def shorten_long_item_names():
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


def add_website_item_length_setters():
    """
    Runs before migrate. The length 255 setters are in website_rigpl/custom/website_item.json,
    but that file syncs after all patches. ERPNext's create_website_items patch copies Item
    names of up to 200 characters, so without the setters it stops at 140.
    """
    missing = [
        field for field in WEBSITE_ITEM_NAME_FIELDS if not frappe.db.exists("Property Setter", setter_name(field))
    ]
    if not missing:
        return
    for field in missing:
        insert_length_setter(field)
    frappe.clear_cache(doctype=WEBSITE_ITEM)
    # A failed migrate can leave the table at 140, and reload_doc does not widen it if the JSON did not change.
    if frappe.db.exists("DocType", WEBSITE_ITEM):
        frappe.db.updatedb(WEBSITE_ITEM)
    print(f"Added {WEBSITE_ITEM} length setters: {', '.join(missing)}")


def insert_length_setter(field):
    # db_insert: on a v12 database Website Item does not exist yet, so Document.insert fails link validation.
    frappe.get_doc(
        {
            "doctype": "Property Setter",
            "name": setter_name(field),
            "owner": "Administrator",
            "doctype_or_field": "DocField",
            "doc_type": WEBSITE_ITEM,
            "field_name": field,
            "property": "length",
            "property_type": "Int",
            "value": "255",
        }
    ).db_insert()


def setter_name(field):
    return f"{WEBSITE_ITEM}-{field}-length"
