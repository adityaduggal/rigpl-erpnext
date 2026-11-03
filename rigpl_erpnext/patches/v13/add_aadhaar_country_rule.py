import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.permissions import add_permission, update_permission_property


def execute():
    """
    #194: Aadhaar rules apply to Employees of a Branch whose Country has aadhaar_applicable.
    The Country field is made here with create_custom_field (as add_has_priority_to_pricing_rule
    does), so it exists before India gets the flag.
    Employee.allow_duplicate_aadhaar is on permlevel 2, which only a System Manager can write.
    """
    create_custom_field(
        "Country",
        {
            "fieldname": "aadhaar_applicable",
            "fieldtype": "Check",
            "label": "Aadhaar Applicable",
            "insert_after": "pincode_regular_expression",
            "default": "0",
        },
    )
    if frappe.db.exists("Country", "India"):
        frappe.db.set_value("Country", "India", "aadhaar_applicable", 1, update_modified=False)

    for role in ("System Manager", "HR Manager", "HR User"):
        add_permission("Employee", role, permlevel=2)
    update_permission_property("Employee", "System Manager", 2, "write", 1)
    frappe.clear_cache(doctype="Employee")
