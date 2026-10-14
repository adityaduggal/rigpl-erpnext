import frappe


def execute():
    """
    The RIGPL web templates belong to the module Website-RIGPL, which is in
    modules.txt but has no Module Def on sites installed before it was added.
    """
    if not frappe.db.exists("Module Def", "Website-RIGPL"):
        frappe.get_doc(
            {"doctype": "Module Def", "module_name": "Website-RIGPL", "app_name": "rigpl_erpnext"}
        ).insert(ignore_permissions=True)
