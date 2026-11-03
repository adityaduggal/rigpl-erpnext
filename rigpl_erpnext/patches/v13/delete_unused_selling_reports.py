import frappe

REPORTS = ("Sales Partner Commission Details", "SI Import to RIGB RU")


def execute():
    """
    These 2 reports were not opened since 2020-10 and their code is deleted (#187). Delete the
    Report rows, so the desk does not show a report without code. Idempotent.
    """
    for name in REPORTS:
        if frappe.db.exists("Report", name):
            frappe.delete_doc("Report", name, force=True, ignore_permissions=True)
            print(f"Deleted the unused report {name}.")
