import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import IfNull


def execute():
    """
    ERPNext v13 adds Lead.designation as a standard Link to Designation. The old
    v12 Custom Field with the same fieldname makes sync_customizations fail with
    UniqueFieldnameError. Removes the Custom Field and clears free-text values
    which would fail link validation on save. The column is kept, so valid values
    stay in place.
    """
    custom_field = frappe.db.get_value("Custom Field", {"dt": "Lead", "fieldname": "designation"})
    if custom_field:
        frappe.delete_doc("Custom Field", custom_field, ignore_permissions=True)

    lead = DocType("Lead")
    designation = DocType("Designation")
    (
        frappe.qb.update(lead)
        .set(lead.designation, None)
        .where(IfNull(lead.designation, "") != "")
        .where(lead.designation.notin(frappe.qb.from_(designation).select(designation.name)))
    ).run()
