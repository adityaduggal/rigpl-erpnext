import frappe

INDEXES = (["status", "docstatus"], ["published"], ["awb_number"], ["carrier_name"])


def execute():
    """#168, #152: the tracking jobs, the webhook lookup by AWB and the report filter on these.
    add_index does nothing when the index exists."""
    for fields in INDEXES:
        frappe.db.add_index("Carrier Tracking", fields)
