import frappe

INDEXES = (["parent", "attribute"], ["attribute", "attribute_value"])


def execute():
    """
    Item attribute queries (#131) look up the attribute rows of an item, and the items that
    have an attribute value. The table has only single-column `parent` and `attribute` indexes.
    Add `(parent, attribute)` and `(attribute, attribute_value)`. `add_index` skips an index
    that exists, so this patch can run again.
    """
    for fields in INDEXES:
        frappe.db.add_index("Item Variant Attribute", fields)
        print(f"Item Variant Attribute: index on ({', '.join(fields)}) is in place.")
