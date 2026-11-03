"""
Finds the provider adapter of a Transporter (#168). A new provider needs one module in
`providers/` and one entry in PROVIDERS.
"""
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import frappe
from frappe.utils.password import get_decrypted_password

from .accounts import BOOKING, NONE, TRACKING_ONLY
from .base import Account, NotSupported, ShippingProvider
from .status_map import StatusResolver

SECRET_FIELDS = ("client_secret", "api_key", "password", "webhook_secret")
ACCOUNT_FIELDS = ("name", "provider", "enabled", "is_sandbox", "account_number", "customer_code", "client_id",
                  "username", "base_url", "tracking_base_url", "serviceability_url", "webhook_enabled")


def provider_classes() -> Dict[str, type]:
    from .providers.dtdc import DTDC
    from .providers.fedex import FedEx
    from .providers.shipway import Shipway

    return {"DTDC": DTDC, "FedEx": FedEx, "Shipway": Shipway}


@dataclass
class Carrier:
    """A Transporter with its adapter."""
    transporter: str
    provider: ShippingProvider
    api_mode: str
    service_code: str

    @property
    def can_book(self) -> bool:
        return self.api_mode == BOOKING

    @property
    def can_track(self) -> bool:
        return self.api_mode in (BOOKING, TRACKING_ONLY)


def load_accounts(names: Iterable[str]) -> Dict[str, Account]:
    """The enabled accounts with their secrets: 1 query, plus 1 for each secret that is set."""
    names = [n for n in set(names) if n]
    if not names:
        return {}
    rows = frappe.get_all("Shipping Provider Account", filters={"name": ["in", names], "enabled": 1},
                          fields=list(ACCOUNT_FIELDS))
    accounts = {}
    for row in rows:
        secrets = {f: get_decrypted_password("Shipping Provider Account", row.name, f, raise_exception=False) or ""
                   for f in SECRET_FIELDS}
        values = {k: row.get(k) or "" for k in ACCOUNT_FIELDS if k != "enabled"}
        values["is_sandbox"] = bool(row.is_sandbox)
        values["webhook_enabled"] = bool(row.webhook_enabled)
        accounts[row.name] = Account(**values, **secrets)
    return accounts


def get_carriers(transporters: Iterable[str]) -> Dict[str, Carrier]:
    """{transporter: Carrier} for the Transporters with an API mode and an enabled account.
    2 queries for any number of Transporters (plus the secrets of each account)."""
    transporters = [t for t in set(transporters) if t]
    if not transporters:
        return {}
    rows = frappe.get_all("Transporters", filters={"name": ["in", transporters], "api_mode": ["!=", NONE]},
                          fields=["name", "shipping_provider_account", "api_mode", "provider_service_code"])
    accounts = load_accounts(r.shipping_provider_account for r in rows)
    classes = provider_classes()
    carriers, resolvers = {}, {}
    for row in rows:
        account = accounts.get(row.shipping_provider_account)
        if not account or account.provider not in classes:
            continue
        if account.provider not in resolvers:
            resolvers[account.provider] = StatusResolver(account.provider)
        provider = classes[account.provider](account, resolve=resolvers[account.provider])
        carriers[row.name] = Carrier(row.name, provider, row.api_mode, row.provider_service_code or "")
    return carriers


def transporter_api(transporter: str) -> Tuple[str, str]:
    """(provider, api_mode) of a Transporter from the cache, without the secrets.
    ("", "None") when it has no API."""
    if not transporter:
        return "", NONE
    api_mode, account = frappe.get_cached_value("Transporters", transporter, ["api_mode", "shipping_provider_account"]) \
        or (NONE, None)
    if not account or not api_mode or api_mode == NONE:
        return "", NONE
    provider, enabled = frappe.get_cached_value("Shipping Provider Account", account, ["provider", "enabled"]) or ("", 0)
    return (provider, api_mode) if enabled else ("", NONE)


def get_carrier(transporter: str) -> Optional[Carrier]:
    return get_carriers([transporter]).get(transporter)


def require_carrier(transporter: str, capability: str, booking: bool = False) -> Carrier:
    """The Carrier of a Transporter that can do `capability`, or a clear error for the user."""
    carrier = get_carrier(transporter)
    link = frappe.get_desk_link("Transporters", transporter)
    if not carrier:
        frappe.throw(f"{link} has no API mode, or its Shipping Provider Account is missing or disabled.",
                     title="No Shipping API")
    if booking and not carrier.can_book:
        frappe.throw(f"{link} has API Mode {carrier.api_mode}. Booking needs Booking and Tracking.",
                     title="Booking Not Allowed")
    if not carrier.provider.supports(capability):
        raise NotSupported(f"{carrier.provider.name} does not support {capability} yet")
    return carrier
