import frappe


def execute():
    """
    Pending Production Orders read Work Order, which is not used now: all Work Orders with open
    qty are cancelled. Its code is deleted (#187). Delete the Report row, so the desk does not
    show a report without code. Idempotent.
    """
    name = "Pending Production Orders"
    if frappe.db.exists("Report", name):
        frappe.delete_doc("Report", name, force=True, ignore_permissions=True)
        print(f"Deleted the unused report {name}.")
