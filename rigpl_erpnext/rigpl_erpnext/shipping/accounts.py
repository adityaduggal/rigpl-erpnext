#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
Moves the carrier API data from the old Transporters fields to Shipping Provider Account
(#168). The old fields are in rohit_common and are removed later (rohit-common#27).

- One account for each distinct set of credentials of a provider.
- Each Transporter gets `shipping_provider_account`, `api_mode` and `provider_service_code`.
"""
from typing import Dict, List, Optional, Tuple

import frappe

from ...utils.batch_write_utils import bulk_set_fields

NONE, TRACKING_ONLY, BOOKING = "None", "Tracking Only", "Booking and Tracking"

TRANSPORTER_FIELDS = [
    {
        "fieldname": "sb_shipping_api",
        "fieldtype": "Section Break",
        "label": "Shipping API",
        "insert_after": "port_code",
        "collapsible": 1,
    },
    {
        "fieldname": "shipping_provider_account",
        "fieldtype": "Link",
        "label": "Shipping Provider Account",
        "options": "Shipping Provider Account",
        "insert_after": "sb_shipping_api",
    },
    {
        "fieldname": "api_mode",
        "fieldtype": "Select",
        "label": "API Mode",
        "options": "\n".join((NONE, TRACKING_ONLY, BOOKING)),
        "default": NONE,
        "insert_after": "shipping_provider_account",
        "description": "Tracking Only: the code only tracks. Booking and Tracking: it also books, cancels and gets labels.",
    },
    {
        "fieldname": "provider_service_code",
        "fieldtype": "Data",
        "label": "Provider Service Code",
        "insert_after": "api_mode",
        "description": "FedEx service type (for example INTERNATIONAL_PRIORITY), DTDC service type (for example PRIORITY) or Shipway carrier id.",
    },
]

OLD_FIELDS = [
    "name", "track_on_shipway", "shipway_id",
    "fedex_credentials", "fedex_tracking_only", "fedex_service_code", "fedex_account_number", "is_test_server",
    "dtdc_credentials", "dtdc_tracking_only", "dtdc_service_id", "api_key", "dtdc_customer_code",
    "dtdc_tracking_username", "dtdc_tracking_password", "dtdc_base_link", "dtdc_tracking_base_link",
    "dtdc_service_validation_link", "shipping_provider_account", "api_mode", "provider_service_code",
]


def provider_and_mode(row: dict) -> Tuple[Optional[str], str]:
    """The provider and the API mode from the 5 old checkboxes. One is set at most."""
    if row.get("fedex_credentials"):
        return "FedEx", BOOKING
    if row.get("fedex_tracking_only"):
        return "FedEx", TRACKING_ONLY
    if row.get("dtdc_credentials"):
        return "DTDC", BOOKING
    if row.get("dtdc_tracking_only"):
        return "DTDC", TRACKING_ONLY
    if row.get("track_on_shipway"):
        return "Shipway", TRACKING_ONLY
    return None, NONE


def account_values(provider: str, row: dict, shipway: dict) -> dict:
    """The fields of the account for a Transporter row. Secrets go to Password fields.
    FedEx REST needs a new client id and secret, so the SOAP key and password are not copied."""
    if provider == "FedEx":
        return {"account_number": row.get("fedex_account_number"), "is_sandbox": row.get("is_test_server") or 0}
    if provider == "DTDC":
        return {
            "customer_code": row.get("dtdc_customer_code"),
            "api_key": row.get("api_key"),
            "username": row.get("dtdc_tracking_username"),
            "password": row.get("dtdc_tracking_password"),
            "base_url": row.get("dtdc_base_link"),
            "tracking_base_url": row.get("dtdc_tracking_base_link"),
            "serviceability_url": row.get("dtdc_service_validation_link"),
        }
    return {"username": shipway.get("username"), "password": shipway.get("license_key")}


def service_code(provider: str, row: dict) -> Optional[str]:
    if provider == "FedEx":
        return row.get("fedex_service_code")
    if provider == "DTDC":
        return row.get("dtdc_service_id")
    return str(row["shipway_id"]) if row.get("shipway_id") else None


def account_name(provider: str, values: dict, taken: set) -> str:
    """For example "FedEx 1234567", "DTDC AB123" or "Shipway". A number is added if taken."""
    base = " ".join(filter(None, (provider, values.get("account_number") or values.get("customer_code"))))
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base} {n}"
    return name


def plan_accounts(rows: List[dict], shipway: dict, taken: set) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """Pure: ({account name: account values}, {transporter: new fields}) for the Transporters
    that have a provider and no account yet. Rows with the same credentials share one account."""
    accounts, by_key, links = {}, {}, {}
    for row in rows:
        provider, mode = provider_and_mode(row)
        if not provider or row.get("shipping_provider_account"):
            continue
        values = account_values(provider, row, shipway)
        key = (provider, tuple(sorted((k, v or "") for k, v in values.items())))
        if key not in by_key:
            name = account_name(provider, values, taken | set(accounts))
            by_key[key] = name
            accounts[name] = dict(values, provider=provider)
        links[row["name"]] = {
            "shipping_provider_account": by_key[key],
            "api_mode": mode,
            "provider_service_code": service_code(provider, row),
        }
    return accounts, links


def migrate_transporters() -> Dict[str, int]:
    """Makes the accounts and links the Transporters. Safe to run again: linked Transporters
    are skipped. 3 reads, then 1 insert for each account and 1 UPDATE for each set of values."""
    rows = frappe.get_all("Transporters", fields=OLD_FIELDS)
    shipway = frappe.db.get_singles_dict("Shipway Settings")
    taken = set(frappe.get_all("Shipping Provider Account", pluck="name"))
    accounts, links = plan_accounts(rows, shipway, taken)

    for name, values in accounts.items():
        frappe.get_doc(dict(values, doctype="Shipping Provider Account", account_name=name, enabled=1)).insert(
            ignore_permissions=True
        )
    old = {row["name"]: {field: row.get(field) for field in links.get(row["name"], {})} for row in rows}
    bulk_set_fields("Transporters", links, old)
    return {"accounts": len(accounts), "transporters": len(links)}
