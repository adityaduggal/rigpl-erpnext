import frappe


def execute():
    """
    The draft Job Cards of an item and operation (check_existing_job_card, the next Job Card
    and return_job_card_qty) are found by `production_item`, `operation` and `docstatus`.
    `add_index` skips an index that exists, so this patch can run again.
    """
    frappe.db.add_index("Process Job Card RIGPL", ["production_item", "operation", "docstatus"])
    print("Process Job Card RIGPL: index on (production_item, operation, docstatus) is in place.")
