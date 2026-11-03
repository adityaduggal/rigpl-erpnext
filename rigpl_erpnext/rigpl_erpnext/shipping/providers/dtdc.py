"""
DTDC (#168). Booking, labels and cancel use Shipsy (`app.shipsy.in`). Tracking uses the DTDC
tracking service (`blktracksvc.dtdc.com`), which takes one AWB for each call. Serviceability
uses `PincodeApiCall`.

The Shipsy docs for cancel, POD and webhooks are not public. `cancel` uses the Shipsy
`consignment/cancel` call; check it on a TEST booking before you use it on a real one.
"""
import base64
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from .. import status as st
from ..seed_rules import SEED_RULES
from ..base import BookingResult, Label, NotSupported, ProviderError, Scan, ShipmentRequest, ShippingProvider, TrackingResult
from ..http import cached_token, clear_token, json_or_error, request

BASE_URL = "https://app.shipsy.in/api/customer/integration/consignment/"
TRACKING_URL = "https://blktracksvc.dtdc.com/dtdc-api/"
SERVICEABILITY_URL = "https://smarttrack-ctbsplus.dtdc.com/ratecalapi/PincodeApiCall"
TOKEN_SECONDS = 30 * 60



def parse_datetime(day: str, time: str = "") -> Optional[datetime]:
    """DTDC dates are ddmmyyyy, and times are HHMM, HH:MM or HH:MM:SS."""
    day, time = (day or "").strip(), (time or "").strip().replace(":", "")
    if not day:
        return None
    try:
        return datetime.strptime(day + time[:4].ljust(4, "0"), "%d%m%Y%H%M")
    except ValueError:
        return None


def parse_date(day: str) -> Optional[date]:
    value = parse_datetime(day)
    return value.date() if value and value.year > 1900 else None


def parse_tracking(awb: str, data: dict, resolve) -> TrackingResult:
    """A TrackingResult from a getTrackDetails reply. `resolve(code, text)` maps the code."""
    if data.get("statusCode") != 200 or not data.get("trackHeader"):
        return TrackingResult(awb=awb, status=st.NO_INFORMATION, found=False)
    header = data["trackHeader"]
    scans = []
    for row in data.get("trackDetails") or []:
        time = parse_datetime(row.get("strActionDate"), row.get("strActionTime"))
        if not time:
            continue
        detail = f"{row.get('strCode', '')}: {row.get('strAction', '')}-{row.get('strManifestNo', '')} {row.get('sTrRemarks', '')}"
        scans.append(Scan(
            time=time,
            location=f"Frm: {row.get('strOrigin', '')} To: {row.get('strDestination', '')}"[:140],
            status_detail=detail.strip()[:140],
        ))
    scans.sort(key=lambda s: s.time)
    latest_code = scans[-1].status_detail.split(":", 1)[0] if scans else ""
    status = resolve(latest_code, header.get("strStatus") or "") or st.IN_TRANSIT
    delivered = parse_datetime(header.get("strStatusTransOn"), header.get("strStatusTransTime")) \
        if status == st.DELIVERED else None
    recipient = " ".join(filter(None, (header.get("strRemarks"), header.get("strStatusRelName")))).strip()
    return TrackingResult(
        awb=awb,
        status=status,
        status_code=latest_code or (header.get("strStatus") or "")[:20],
        pickup_date=parse_datetime(header.get("strBookedDate"), header.get("strBookedTime")),
        expected_delivery_date=parse_date(header.get("strExpectedDeliveryDate")),
        delivery_date_time=delivered or (scans[-1].time if status == st.DELIVERED and scans else None),
        recipient=recipient[:140],
        destination=(header.get("strDestination") or "")[:140],
        scans=scans,
    )


def booking_json(req: ShipmentRequest, customer_code: str) -> dict:
    """The Shipsy softdata body for one consignment. A test has TEST-RIGPL in its reference."""
    reference = "-".join(req.references)
    description = f"{req.description} {'TEST - DO NOT PICK UP' if req.test_marking else ''}".strip()
    consignment = {
        "customer_code": customer_code,
        "service_type_id": req.service_code,
        "consignment_type": "reverse" if req.is_inward else "forward",
        "load_type": "NON-DOCUMENT",
        "description": description,
        "commodity_id": req.description,
        "cod_amount": 0,
        "weight_unit": "kg",
        "weight": round(sum(p.weight for p in req.packages), 3),
        "declared_value": req.declared_value,
        "num_pieces": len(req.packages),
        "is_risk_surcharge_applicable": "false",
        "customer_reference_number": reference,
        "origin_details": dtdc_address(req.origin),
        "destination_details": dtdc_address(req.destination),
        "pieces_detail": [
            {
                "description": description,
                "declared_value": p.declared_value or req.declared_value,
                "weight": p.weight,
                "weight_unit": "kg",
                "height": p.height,
                "length": p.length,
                "width": p.width,
            }
            for p in req.packages
        ],
    }
    if req.invoice_number:
        consignment["invoice_number"] = req.invoice_number
    return {"consignments": [consignment]}


def dtdc_address(address) -> dict:
    return {
        "name": address.name,
        "phone": address.phone,
        "address_line_1": address.line1,
        "address_line_2": address.line2,
        "pincode": address.pincode,
        "city": address.city,
        "state": address.state,
    }


class DTDC(ShippingProvider):
    name = "DTDC"
    capabilities = frozenset(("book", "label", "cancel", "track", "serviceability"))
    track_batch_size = 50
    SEED_RULES = SEED_RULES["DTDC"]

    @property
    def base_url(self) -> str:
        return (self.account.base_url or BASE_URL).rstrip("/") + "/"

    @property
    def tracking_url(self) -> str:
        return (self.account.tracking_base_url or TRACKING_URL).rstrip("/") + "/"

    def shipsy_headers(self) -> dict:
        if not self.account.api_key:
            raise ProviderError(f"DTDC: Shipping Provider Account {self.account.name} has no API Key")
        return {"api-key": self.account.api_key}

    def book(self, req: ShipmentRequest) -> BookingResult:
        reply = json_or_error(request("POST", self.base_url + "softdata", self.name, headers=self.shipsy_headers(),
                                      json=booking_json(req, self.account.customer_code)), self.name)
        data = (reply.get("data") or [{}])[0] if reply.get("status") == "OK" else {}
        if not data.get("success"):
            raise ProviderError(f"DTDC: booking of {req.reference} failed: {data.get('message') or reply}")
        awb = data.get("reference_number")
        pieces = [p.get("reference_number") for p in data.get("pieces") or []]
        return BookingResult(awb=awb, package_ids=pieces, labels=self.get_labels(awb), raw=reply)

    def get_labels(self, awb: str) -> List[Label]:
        reply = json_or_error(request("POST", self.base_url + "label/multipiece/", self.name,
                                      headers=self.shipsy_headers(), json={"reference_number": awb}), self.name)
        if reply.get("status") != "OK":
            raise ProviderError(f"DTDC: no label for {awb}: {reply.get('message') or reply.get('status')}")
        return [Label(f"DTDC-{row.get('reference_number')}.pdf", base64.b64decode(row.get("label")))
                for row in reply.get("data") or [] if row.get("label")]

    def cancel(self, awb: str) -> None:
        reply = json_or_error(request("POST", self.base_url + "cancel", self.name, headers=self.shipsy_headers(),
                                      json={"AWBNo": [awb], "customerCode": self.account.customer_code}), self.name)
        if reply.get("status") not in ("OK", "Success", True) and not reply.get("success"):
            raise ProviderError(f"DTDC: cancel of {awb} failed: {reply}")

    def check_serviceability(self, origin_pincode: str, destination_pincode: str, cod: bool = False) -> Tuple[bool, str]:
        url = self.account.serviceability_url or SERVICEABILITY_URL
        reply = json_or_error(request("POST", url, self.name,
                                      json={"orgPincode": origin_pincode, "desPincode": destination_pincode}), self.name)
        zip_resp = (reply.get("ZIPCODE_RESP") or [{}])[0]
        pins = reply.get("PIN_CITY")
        if zip_resp.get("SERVFLAG") == "N" or not isinstance(pins, list):
            return False, f"No DTDC service between PIN codes {origin_pincode} and {destination_pincode}"
        if cod and zip_resp.get("SERV_COD") == "N":
            return False, f"DTDC has no COD service at {destination_pincode}"
        return True, "\n".join(f"PIN Code: {p.get('PIN')} Type of Services: {p.get('PARTIALSERV_AREA_AND_CITY')}"
                               for p in pins)

    def token(self) -> str:
        def fetch():
            if not (self.account.username and self.account.password):
                raise ProviderError(f"DTDC: Shipping Provider Account {self.account.name} has no tracking user")
            reply = request("GET", self.tracking_url + "api/dtdc/authenticate", self.name,
                            params={"username": self.account.username, "password": self.account.password})
            if reply.status_code != 200 or not reply.text.strip():
                raise ProviderError(f"DTDC: tracking login failed with HTTP {reply.status_code}")
            return reply.text.strip(), TOKEN_SECONDS

        return cached_token(f"dtdc:{self.account.name}", fetch)

    def track_one(self, awb: str, token: str) -> Optional[dict]:
        reply = request("POST", self.tracking_url + "rest/JSONCnTrk/getTrackDetails", self.name,
                        headers={"X-Access-Token": token}, json={"trkType": "cnno", "strcnno": awb, "addtnlDtl": "Y"})
        if reply.status_code in (401, 403):
            return None
        return json_or_error(reply, self.name)

    def track_many(self, shipments: Dict[str, str]) -> Dict[str, TrackingResult]:
        """One login for the batch, then one call for each AWB (the API takes one).
        On 401 the token is renewed once."""
        results, token = {}, self.token()
        for awb in shipments:
            data = self.track_one(awb, token)
            if data is None:
                clear_token(f"dtdc:{self.account.name}")
                token = self.token()
                data = self.track_one(awb, token) or {}
            results[awb] = parse_tracking(awb, data, self.resolve)
        return results

    def get_pod(self, awb: str) -> Label:
        raise NotSupported("DTDC proof of delivery waits for the Shipsy POD docs (#171)")
