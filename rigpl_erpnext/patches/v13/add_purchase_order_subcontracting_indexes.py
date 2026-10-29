import frappe


def execute():
    """
    Purchase Order validation (#144) finds the POs of a Job Card by `reference_dt` and
    `reference_dn`, the Made to Order Item Attributes of the PO rows by `sales_order_item`, and
    the attribute Pricing Rules by `supplier`. `add_index` skips an index that exists.
    """
    frappe.db.add_index("Purchase Order Item", ["reference_dt", "reference_dn"], "idx_poi_reference")
    frappe.db.add_index(
        "Made to Order Item Attributes",
        ["sales_order_item", "item_code", "docstatus"],
        "idx_mto_so_item",
    )
    frappe.db.add_index("Pricing Rule", ["supplier"], "idx_pricing_rule_supplier")
    print("Purchase Order Item, Made to Order Item Attributes and Pricing Rule indexes are in place.")
