import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from rigpl_erpnext.rigpl_erpnext.shipping.accounts import TRANSPORTER_FIELDS, migrate_transporters


def execute():
    """
    #168: the carrier API data moves from the old Transporters fields to Shipping Provider
    Account. Patches run before the DocType sync, so the DocType and the custom fields are
    made here. No API call is made.
    """
    frappe.reload_doc("rigpl_erpnext", "doctype", "shipping_provider_account")
    create_custom_fields({"Transporters": TRANSPORTER_FIELDS}, update=True)
    counts = migrate_transporters()
    print(f"Shipping Provider Accounts made: {counts['accounts']}, Transporters linked: {counts['transporters']}")
