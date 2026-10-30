import frappe

OLD_REPORTS = ("Orders To Dispatch", "Pending Orders With Stock Status")


def execute():
    """
    The 2 non-standard Query Reports become standard Script Reports of RIGPL ERPNext (#182).
    Delete the old rows, so the migrate sync after the patches creates the standard reports.
    Idempotent.
    """
    for name in OLD_REPORTS:
        if frappe.db.get_value("Report", name, "is_standard") == "No":
            frappe.delete_doc("Report", name, force=True, ignore_permissions=True)
            print(f"Deleted the old Query Report {name}.")
