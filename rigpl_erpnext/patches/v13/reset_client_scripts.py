import frappe


def execute():
    """
    This Patch would delete all the old Client Scripts
    """
    oscr = frappe.get_all("Client Script")
    for script in oscr:
        frappe.delete_doc("Client Script", script.name)
        print(f"Deleted: {script.name} old Client Script")
