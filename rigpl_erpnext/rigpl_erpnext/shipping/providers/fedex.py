"""
FedEx REST API (#170). It replaces the retired SOAP `fedex` library.

- OAuth client credentials: the API Key is `client_id` and the Secret Key is
  `client_secret` on the Shipping Provider Account. The token is cached in Redis.
- Labels come back with the booking, so there is no `label` capability (REST has no reprint).
- The bodies and parsers are in `fedex_payloads.py`.
- Exports send our invoice electronically (ETD, #240): it is uploaded to the document API
  just before the booking, and the booking names its docId.
"""
import json
from datetime import date
from typing import Dict, List, Tuple

from frappe.utils import escape_html, get_time_zone

from ..base import (Address, BookingResult, Label, NotSupported, PreviewContext, ProviderError, Rate, ShipmentRequest,
                    ShippingProvider, TrackingResult)
from ..http import cached_token, clear_token, json_or_error, redact, request, step
from ..seed_rules import SEED_RULES
from . import fedex_payloads as fp

PRODUCTION_URL = "https://apis.fedex.com"
SANDBOX_URL = "https://apis-sandbox.fedex.com"
# The Trade Documents Upload API has its own hosts (servers of the FedEx OpenAPI file)
DOCUMENT_URL = "https://documentapi.prod.fedex.com"
DOCUMENT_SANDBOX_URL = "https://documentapitest.prod.fedex.com/sandbox"
RATE_PATH = "/rate/v1/rates/quotes"
SHIP_PATH = "/ship/v1/shipments"
CANCEL_PATH = "/ship/v1/shipments/cancel"
UPLOAD_PATH = "/documents/v1/etds/encodedmultiupload"
TRACK_PATH = "/track/v1/trackingnumbers"
POD_PATH = "/track/v1/trackingdocuments"
ADDRESS_PATH = "/address/v1/addresses/resolve"
TRANSIT_PATH = "/availability/v1/transittimes"


class FedEx(ShippingProvider):
    name = "FedEx"
    capabilities = frozenset(("rate", "book", "cancel", "track", "pod", "address", "serviceability", "etd", "preview"))
    track_batch_size = 30  # the most FedEx takes in one trackingnumbers call
    check_service_before_booking = False  # the rate quote before booking already checks it
    SEED_RULES = SEED_RULES["FedEx"]

    def get_rates(self, req: ShipmentRequest) -> List[Rate]:
        reply = self.call("POST", RATE_PATH, fp.rate_body(req, self.account_number))
        rates = fp.parse_rates(reply)
        if not rates:
            raise ProviderError(f"FedEx gave no rate for {req.reference}")
        return rates

    def book(self, req: ShipmentRequest) -> BookingResult:
        doc_ids = self.upload_documents(req) if req.documents else []
        result = fp.parse_ship(self.call("POST", SHIP_PATH, fp.ship_body(req, self.account_number, doc_ids)),
                               req.reference)
        if not result.awb:
            raise ProviderError(f"FedEx: booking of {req.reference} gave no tracking number")
        return result

    def preview(self, action: str, ctx: PreviewContext) -> List[dict]:
        """The calls of a form action, with the bodies that the real call sends. Nothing is sent."""
        req, awb, base = ctx.request, ctx.awb, self.base_url
        login = step("Login (only when the token has expired)", "POST", base + "/oauth/token",
                     {"grant_type": "client_credentials", "client_id": "<API Key>", "client_secret": "<hidden>"})
        if action in ("get_rates", "book_shipment"):
            steps = [login, step("Rate", "POST", base + RATE_PATH, fp.rate_body(req, self.account_number))]
            if action == "get_rates":
                return steps
            doc_ids = [f"<docId of {d.filename}>" for d in req.documents]
            if req.documents:
                steps.append(step("Upload documents", "POST", self.document_url + UPLOAD_PATH, fp.upload_body(req)))
            return steps + [step("Ship", "POST", base + SHIP_PATH, fp.ship_body(req, self.account_number, doc_ids))]
        calls = {
            "available_services": lambda: ("Transit times", "POST", TRANSIT_PATH,
                                           fp.transit_body(req.origin, req.destination, date.today())),
            "address_validation": lambda: ("Address check", "POST", ADDRESS_PATH, fp.address_body(req.destination)),
            "get_status": lambda: ("Tracking", "POST", TRACK_PATH, fp.track_body([awb])),
            "get_pod": lambda: ("Proof of delivery", "POST", POD_PATH, fp.pod_body(awb)),
            "delete_shipment": lambda: ("Cancel", "PUT", CANCEL_PATH, fp.cancel_body(awb, self.account_number)),
        }
        if action not in calls:
            raise NotSupported(f"FedEx: no preview for {action}")
        name, method, path, body = calls[action]()
        return [login, step(name, method, base + path, body)]

    def upload_documents(self, req: ShipmentRequest) -> List[str]:
        reply = self.call("POST", UPLOAD_PATH, fp.upload_body(req), base=self.document_url)
        doc_ids = fp.parse_upload(reply, req)
        missing = [d.filename for d, doc_id in zip(req.documents, doc_ids) if not doc_id]
        if missing:
            # a reply of a shape that we do not know is shown as it is (#244)
            reason = fp.error_text(reply) or "FedEx reply: " + escape_html(json.dumps(redact(reply, 500))[:1000])
            raise ProviderError(f"FedEx did not take the trade documents {', '.join(missing)} of {req.reference}. "
                                + reason)
        return doc_ids

    def cancel(self, awb: str) -> None:
        reply = self.call("PUT", CANCEL_PATH, fp.cancel_body(awb, self.account_number))
        if not (reply.get("output") or {}).get("cancelledShipment"):
            raise ProviderError(f"FedEx: cancel of {awb} failed: {(reply.get('output') or {}).get('message') or reply}")

    def track_many(self, shipments: Dict[str, str]) -> Dict[str, TrackingResult]:
        """One call for each 30 AWBs. An AWB that FedEx does not return is not found."""
        awbs, tz, results = list(shipments), get_time_zone(), {}
        for start in range(0, len(awbs), self.track_batch_size):
            batch = awbs[start:start + self.track_batch_size]
            items = fp.track_items(self.call("POST", TRACK_PATH, fp.track_body(batch)))
            for awb in batch:
                results[awb] = fp.parse_tracking(awb, items.get(awb), self.resolve, tz)
        return results

    def get_pod(self, awb: str) -> Label:
        label = fp.parse_pod(awb, self.call("POST", POD_PATH, fp.pod_body(awb)))
        if not label:
            raise ProviderError(f"FedEx has no proof of delivery for {awb} yet")
        return label

    def validate_address(self, address: Address) -> str:
        return fp.parse_address(self.call("POST", ADDRESS_PATH, fp.address_body(address)))

    def check_serviceability(self, origin: Address, destination: Address, cod: bool = False) -> Tuple[bool, str]:
        """The FedEx services and transit days between two addresses."""
        lines = fp.parse_transit(self.call("POST", TRANSIT_PATH,
                                           fp.transit_body(origin, destination, date.today())))
        if not lines:
            return False, f"FedEx has no service from {origin.pincode} to {destination.pincode}"
        return True, "\n".join(lines)

    # ------------------------------------------------------------------------------ HTTP

    @property
    def base_url(self) -> str:
        return (self.account.base_url or (SANDBOX_URL if self.account.is_sandbox else PRODUCTION_URL)).rstrip("/")

    @property
    def document_url(self) -> str:
        return DOCUMENT_SANDBOX_URL if self.account.is_sandbox else DOCUMENT_URL

    @property
    def account_number(self) -> str:
        if not self.account.account_number:
            raise ProviderError(f"FedEx: Shipping Provider Account {self.account.name} has no Account Number")
        return self.account.account_number

    @property
    def token_key(self) -> str:
        return f"fedex:{self.account.name}"

    def call(self, method: str, path: str, body: dict, base: str = "") -> dict:
        """A JSON call with the bearer token. A 401 renews the token once. FedEx errors
        become ProviderError with the FedEx code and message."""
        reply = self.send(method, path, body, base)
        if reply.status_code == 401:
            clear_token(self.token_key)
            reply = self.send(method, path, body, base)
        data = json_or_error(reply, self.name)
        # a rejected upload has an output block too (#244)
        if data.get("errors") and (reply.status_code >= 400 or not data.get("output")):
            raise ProviderError("FedEx: " + fp.error_text(data))
        if reply.status_code >= 400 and not data.get("output"):
            raise ProviderError(f"FedEx: {method} {path} gave HTTP {reply.status_code}")
        return data

    def send(self, method: str, path: str, body: dict, base: str = ""):
        headers = {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json", "X-locale": "en_US"}
        return request(method, (base or self.base_url) + path, self.name, headers=headers, json=body)

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
