"""The Shipping section of RIGPL Settings, with the defaults when a field is empty (#168)."""
from dataclasses import dataclass

import frappe
from frappe.utils import cint

DEFAULTS = {
    "unpublish_after_delivery_days": 7,
    "published_ctrack_days": 90,
    "ctrack_auto_close_days": 150,
    "ctrack_poll_hours": 6,
    "ctrack_webhook_poll_hours": 24,
    "max_track_days": 150,
    "shipway_max_track_days": 60,
    "shipway_push_max_days": 20,
}


@dataclass
class ShippingSettings:
    unpublish_after_delivery_days: int
    published_ctrack_days: int
    ctrack_auto_close_days: int
    ctrack_poll_hours: int
    ctrack_webhook_poll_hours: int
    max_track_days: int
    shipway_max_track_days: int
    shipway_push_max_days: int


def get_shipping_settings() -> ShippingSettings:
    doc = frappe.get_cached_doc("RIGPL Settings", "RIGPL Settings")
    return ShippingSettings(**{field: cint(doc.get(field)) or default for field, default in DEFAULTS.items()})
