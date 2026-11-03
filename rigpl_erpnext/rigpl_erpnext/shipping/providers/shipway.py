"""
Shipway (#172), for the couriers with no direct API (Speed Post, UPS, DHL and others).
A tracking is pushed to Shipway once (`push`), then tracked by its order id, which is the
Carrier Tracking name. The carrier id of Shipway is the `provider_service_code` of the
Transporter.
"""
import json
from datetime import datetime
from typing import Dict, Optional

from frappe.utils import get_datetime

from .. import status as st
from ..seed_rules import SEED_RULES
from ..base import ProviderError, Scan, ShippingProvider, TrackingResult
from ..http import json_or_error, request

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


class Shipway(ShippingProvider):
    name = "Shipway"
    capabilities = frozenset(("track", "push"))
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
        reply = self.call("pushOrderData", {
            "carrier_id": service_code, "awb": awb, "order_id": reference, "first_name": "Rohit",
            "last_name": "Cutting Tools", "email": "gmail@gmail.com", "phone": "9999999999", "products": "N/A",
        })
        return reply.get("status") == "Success"
