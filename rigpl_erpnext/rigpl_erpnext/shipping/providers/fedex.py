"""
FedEx REST API (#170). It replaces the retired SOAP `fedex` library.

- OAuth client credentials: the API Key is `client_id` and the Secret Key is
  `client_secret` on the Shipping Provider Account. The token is cached in Redis.
- Labels come back with the booking, so there is no `label` capability (REST has no reprint).
- The bodies and parsers are in `fedex_payloads.py`.
"""
from datetime import date
from typing import Dict, List, Tuple

from frappe.utils import get_time_zone

from ..base import Address, BookingResult, Label, ProviderError, Rate, ShipmentRequest, ShippingProvider, TrackingResult
from ..http import cached_token, clear_token, json_or_error, request
from ..seed_rules import SEED_RULES
from . import fedex_payloads as fp

PRODUCTION_URL = "https://apis.fedex.com"
SANDBOX_URL = "https://apis-sandbox.fedex.com"


class FedEx(ShippingProvider):
    name = "FedEx"
    capabilities = frozenset(("rate", "book", "cancel", "track", "pod", "address", "serviceability"))
    track_batch_size = 30  # the most FedEx takes in one trackingnumbers call
    check_service_before_booking = False  # the rate quote before booking already checks it
    SEED_RULES = SEED_RULES["FedEx"]

    def get_rates(self, req: ShipmentRequest) -> List[Rate]:
        reply = self.call("POST", "/rate/v1/rates/quotes", fp.rate_body(req, self.account_number))
        rates = fp.parse_rates(reply)
        if not rates:
            raise ProviderError(f"FedEx gave no rate for {req.reference}")
        return rates

    def book(self, req: ShipmentRequest) -> BookingResult:
        result = fp.parse_ship(self.call("POST", "/ship/v1/shipments", fp.ship_body(req, self.account_number)),
                               req.reference)
        if not result.awb:
            raise ProviderError(f"FedEx: booking of {req.reference} gave no tracking number")
        return result

    def cancel(self, awb: str) -> None:
        reply = self.call("PUT", "/ship/v1/shipments/cancel", fp.cancel_body(awb, self.account_number))
        if not (reply.get("output") or {}).get("cancelledShipment"):
            raise ProviderError(f"FedEx: cancel of {awb} failed: {(reply.get('output') or {}).get('message') or reply}")

    def track_many(self, shipments: Dict[str, str]) -> Dict[str, TrackingResult]:
        """One call for each 30 AWBs. An AWB that FedEx does not return is not found."""
        awbs, tz, results = list(shipments), get_time_zone(), {}
        for start in range(0, len(awbs), self.track_batch_size):
            batch = awbs[start:start + self.track_batch_size]
            items = fp.track_items(self.call("POST", "/track/v1/trackingnumbers", fp.track_body(batch)))
            for awb in batch:
                results[awb] = fp.parse_tracking(awb, items.get(awb), self.resolve, tz)
        return results

    def get_pod(self, awb: str) -> Label:
        label = fp.parse_pod(awb, self.call("POST", "/track/v1/trackingdocuments", fp.pod_body(awb)))
        if not label:
            raise ProviderError(f"FedEx has no proof of delivery for {awb} yet")
        return label

    def validate_address(self, address: Address) -> str:
        return fp.parse_address(self.call("POST", "/address/v1/addresses/resolve", fp.address_body(address)))

    def check_serviceability(self, origin: Address, destination: Address, cod: bool = False) -> Tuple[bool, str]:
        """The FedEx services and transit days between two addresses."""
        lines = fp.parse_transit(self.call("POST", "/availability/v1/transittimes",
                                           fp.transit_body(origin, destination, date.today())))
        if not lines:
            return False, f"FedEx has no service from {origin.pincode} to {destination.pincode}"
        return True, "\n".join(lines)

    # ------------------------------------------------------------------------------ HTTP

    @property
    def base_url(self) -> str:
        return (self.account.base_url or (SANDBOX_URL if self.account.is_sandbox else PRODUCTION_URL)).rstrip("/")

    @property
    def account_number(self) -> str:
        if not self.account.account_number:
            raise ProviderError(f"FedEx: Shipping Provider Account {self.account.name} has no Account Number")
        return self.account.account_number

    @property
    def token_key(self) -> str:
        return f"fedex:{self.account.name}"

    def call(self, method: str, path: str, body: dict) -> dict:
        """A JSON call with the bearer token. A 401 renews the token once. FedEx errors
        become ProviderError with the FedEx code and message."""
        reply = self.send(method, path, body)
        if reply.status_code == 401:
            clear_token(self.token_key)
            reply = self.send(method, path, body)
        data = json_or_error(reply, self.name)
        errors = data.get("errors") or []
        if errors and not (data.get("output")):
            raise ProviderError("FedEx: " + "; ".join(f"{e.get('code')}: {e.get('message')}" for e in errors)[:500])
        if reply.status_code >= 400 and not data.get("output"):
            raise ProviderError(f"FedEx: {method} {path} gave HTTP {reply.status_code}")
        return data

    def send(self, method: str, path: str, body: dict):
        headers = {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json", "X-locale": "en_US"}
        return request(method, self.base_url + path, self.name, headers=headers, json=body)

    def token(self) -> str:
        def fetch():
            if not (self.account.client_id and self.account.client_secret):
                raise ProviderError(f"FedEx: Shipping Provider Account {self.account.name} needs the REST API Key "
                                    "(Client ID) and Secret Key (Client Secret)")
            reply = request("POST", self.base_url + "/oauth/token", self.name, data={
                "grant_type": "client_credentials", "client_id": self.account.client_id,
                "client_secret": self.account.client_secret})
            data = json_or_error(reply, self.name)
            if reply.status_code != 200 or not data.get("access_token"):
                codes = ", ".join(e.get("code") or "" for e in data.get("errors") or [])
                raise ProviderError(f"FedEx: login of {self.account.name} failed with HTTP {reply.status_code} {codes}")
            return data["access_token"], int(data.get("expires_in") or 3600)

        return cached_token(self.token_key, fetch)
