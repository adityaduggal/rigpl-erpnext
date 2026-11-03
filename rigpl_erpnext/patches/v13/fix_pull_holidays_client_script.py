import frappe

SCRIPT = "holiday_list_form_rigpl"
OLD = "rigpl_erpnext.rigpl_erpnext.validations.holiday_list.pull_holidays"
NEW = "rigpl_erpnext.hr_rigpl.validations.holiday_list.pull_holidays"


def execute():
    """
    The Pull Holidays button of Holiday List called a path that does not exist in v13 (#187).
    Point the Client Script to hr_rigpl. Idempotent.
    """
    script = frappe.db.get_value("Client Script", SCRIPT, "script")
    if not script or OLD not in script:
        return
    frappe.db.set_value("Client Script", SCRIPT, "script", script.replace(OLD, NEW))
    frappe.clear_cache(doctype="Holiday List")
    print(f"Client Script {SCRIPT} now calls {NEW}.")
