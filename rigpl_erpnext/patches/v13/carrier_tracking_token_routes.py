"""
#83: published Carrier Trackings get a random token route in place of `name.lower()`,
so the pages cannot be listed by name. The old routes stop working (no redirect).
The shipment email links to the signed URL in place of the bare route.
Safe to run again: rows that already have a token are skipped.
"""
import frappe

from rigpl_erpnext.rigpl_erpnext.shipping.access import needs_new_route, new_route
from rigpl_erpnext.utils.batch_write_utils import bulk_update_rows

NOTIFICATION = "Material Dispatch Notification"
OLD_LINK, NEW_LINK = "{{ doc.route }}", "{{ doc.get_tracking_url() }}"


def execute():
    rows = frappe.get_all("Carrier Tracking", filters={"published": 1}, fields=["name", "route"])
    values = {r.name: {"route": new_route()} for r in rows if needs_new_route(r.name, r.route)}
    bulk_update_rows("Carrier Tracking", values)
    update_notification()
    from frappe.website.render import clear_cache

    clear_cache()


def update_notification():
    message = frappe.db.get_value("Notification", NOTIFICATION, "message")
    if not message or OLD_LINK not in message:
        print(f"{NOTIFICATION}: no {OLD_LINK} in the message, not changed")
        return
    frappe.db.set_value("Notification", NOTIFICATION, "message", message.replace(OLD_LINK, NEW_LINK),
                        update_modified=False)
