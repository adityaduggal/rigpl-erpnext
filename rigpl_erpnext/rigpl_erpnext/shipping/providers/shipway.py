"""
Shipway (#172), for the couriers with no direct API (Speed Post, UPS, DHL and others).
A tracking is pushed to Shipway once (`push`), then tracked by its order id, which is the
Carrier Tracking name. The carrier id of Shipway is the `provider_service_code` of the
Transporter.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional

from frappe.utils import get_datetime

from .. import status as st
from ..seed_rules import SEED_RULES
from ..base import NotSupported, PreviewContext, ProviderError, Scan, ShippingProvider, TrackingResult
from ..http import json_or_error, request, step

BASE_URL = "https://shipway.in/api/"



def to_datetime(value) -> Optional[datetime]:
    try:
        return get_datetime(value) if value else None
    except Exception:
        return None


def parse_tracking(awb: str, reply: dict, resolve) -> TrackingResult:
    if reply.get("status") != "Success" or not isinstance(reply.get("response"), dict):
        return TrackingResult(awb=awb, status=st.NO_INFORMATION, found=False)
    data = reply["response"]
    code = (data.get("current_status_code") or "").upper()
    status = resolve(code, data.get("current_status") or "") or st.IN_TRANSIT
    scans = []
    for row in data.get("scan") or []:
        time = to_datetime(row.get("time"))
        if time:
            scans.append(Scan(time=time, location=(row.get("location") or "")[:140],
                              status_detail=(row.get("status_detail") or row.get("status") or "")[:140]))
    scans.sort(key=lambda s: s.time)
    return TrackingResult(
        awb=awb,
        status=status,
        status_code=code,
        pickup_date=to_datetime(data.get("pickupdate")),
        delivery_date_time=to_datetime(data.get("time")) if status == st.DELIVERED else None,
        recipient=(data.get("recipient") or "")[:140],
        destination=(data.get("to") or "")[:140],
        scans=scans,
    )


def push_body(reference: str, awb: str, service_code: str) -> dict:
    return {"carrier_id": service_code, "awb": awb, "order_id": reference, "first_name": "Rohit",
            "last_name": "Cutting Tools", "email": "gmail@gmail.com", "phone": "9999999999", "products": "N/A"}


class Shipway(ShippingProvider):
    name = "Shipway"
    capabilities = frozenset(("track", "push", "preview"))
    SEED_RULES = SEED_RULES["Shipway"]

    @property
    def base_url(self) -> str:
        return (self.account.base_url or BASE_URL).rstrip("/") + "/"

    def call(self, method: str, body: dict) -> dict:
        """Shipway's old API reads a JSON body on GET, as the code did before."""
        body = dict(body, username=self.account.username, password=self.account.password)
        return json_or_error(request("GET", self.base_url + method, self.name, data=json.dumps(body)), self.name)

    def track_many(self, shipments: Dict[str, str]) -> Dict[str, TrackingResult]:
        return {awb: parse_tracking(awb, self.call("getOrderShipmentDetails", {"order_id": reference}), self.resolve)
                for awb, reference in shipments.items()}

    def push(self, reference: str, awb: str, service_code: str) -> bool:
        """Sends the AWB to Shipway. True when Shipway has it, also when it was sent before."""
        if self.call("getOrderShipmentDetails", {"order_id": reference}).get("status") == "Success":
            return True
        if not service_code:
            raise ProviderError(f"Shipway: no carrier id (Provider Service Code) for {reference}")
        reply = self.call("pushOrderData", push_body(reference, awb, service_code))
        return reply.get("status") == "Success"

    def preview(self, action: str, ctx: PreviewContext) -> List[dict]:
        """The calls of a form action. Shipway reads the user name and the license key in each
        body: they are not shown. Nothing is sent."""
        check = step("Tracking", "GET", self.base_url + "getOrderShipmentDetails", {"order_id": ctx.reference})
        if action == "get_status":
            return [check]
        if action == "pushdata":
            return [check, step("Push", "GET", self.base_url + "pushOrderData",
                                push_body(ctx.reference, ctx.awb, ctx.service_code))]
        raise NotSupported(f"Shipway: no preview for {action}")
