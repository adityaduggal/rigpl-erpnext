import frappe


def execute():
    """
    The last Job Card of each Sales Order item (#135) is found by `sales_order_item` and
    `docstatus`. Production has this index, but it was added by hand and no code makes it.
    Use the same name, so `add_index` skips it where it exists and adds it on a new site.
    """
    frappe.db.add_index(
        "Process Job Card RIGPL", ["sales_order_item", "docstatus"], "idx_process_job_so_item"
    )
    print("Process Job Card RIGPL: index on (sales_order_item, docstatus) is in place.")
