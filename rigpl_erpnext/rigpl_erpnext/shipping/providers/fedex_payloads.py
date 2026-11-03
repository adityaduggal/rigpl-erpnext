"""
FedEx REST request bodies and reply parsers (#170). Pure: no HTTP and no database, so the
tests use JSON fixtures. `fedex.py` sends the bodies.
"""
import base64
import re
from datetime import date, datetime
from typing import Dict, List, Optional

import pytz

from .. import status as st
from ..base import Address, BookingResult, Commodity, Label, Rate, Scan, ShipmentRequest, TrackingResult

# Customs line for shipments with no invoice items (catalogues, samples), as the SOAP code
PRINTED_MATTER = ("PRINTED TRADE ADVERTISING MATERIAL, CATALOGUES", "49111010")
NOT_FOUND_CODES = ("TRACKING.TRACKINGNUMBER.NOTFOUND", "TRACKING.TRACKINGNUMBER.INVALID")
NO_TIN = ("", "NA")


def rate_body(req: ShipmentRequest, account_number: str) -> dict:
    shipment = shipment_base(req, account_number)
    shipment["shipper"] = {"address": party(req.origin)["address"]}
    shipment["recipient"] = {"address": party(req.destination)["address"]}
    shipment["rateRequestType"] = ["ACCOUNT"]
    # The quote leaves duties out, and FedEx allows only SENDER here
    shipment["customsClearanceDetail"]["dutiesPayment"] = payment("SENDER", account_number)
    return {
        "accountNumber": {"value": account_number},
        "rateRequestControlParameters": {"returnTransitTimes": True},
        "requestedShipment": shipment,
    }


def ship_body(req: ShipmentRequest, account_number: str) -> dict:
    shipment = shipment_base(req, account_number)
    shipment.update({
        "shipper": party(req.origin),
        "recipients": [party(req.destination)],
        "shipDatestamp": (req.ship_date or date.today()).isoformat(),
        "shippingChargesPayment": payment("SENDER", account_number),
        "labelSpecification": {
            "imageType": "PDF",
            "labelStockType": "PAPER_85X11_TOP_HALF_LABEL",
            "labelFormatType": "COMMON2D",
            "labelPrintingOrientation": "BOTTOM_EDGE_OF_TEXT_FIRST",
        },
    })
    for line in shipment["requestedPackageLineItems"]:
        line["customerReferences"] = customer_references(req)
    if needs_commercial_invoice(req):
        shipment["customsClearanceDetail"]["commercialInvoice"]["customerReferences"] = [
            {"customerReferenceType": "INVOICE_NUMBER", "value": req.invoice_number}]
        shipment["shippingDocumentSpecification"] = {
            "shippingDocumentTypes": ["COMMERCIAL_INVOICE"],
            "commercialInvoiceDetail": {"documentFormat": {"docType": "PDF", "stockType": "PAPER_LETTER"}},
        }
    return {"labelResponseOptions": "LABEL", "accountNumber": {"value": account_number}, "requestedShipment": shipment}


def parse_rates(reply: dict) -> List[Rate]:
    rates = []
    for detail in (reply.get("output") or {}).get("rateReplyDetails") or []:
        rated = (detail.get("ratedShipmentDetails") or [{}])[0]
        surcharges = (rated.get("shipmentRateDetail") or {}).get("surCharges") or []
        rates.append(Rate(
            service_code=detail.get("serviceType") or "",
            amount=float(rated.get("totalNetFedExCharge") or rated.get("totalNetCharge") or 0),
            currency=rated.get("currency") or "",
            transit_days=transit_days(detail),
            delivery_date=delivery_date(detail),
            oda=any(s.get("type") == "OUT_OF_DELIVERY_AREA" for s in surcharges),
            raw=detail,
        ))
    return rates


def parse_ship(reply: dict, reference: str) -> BookingResult:
    shipment = ((reply.get("output") or {}).get("transactionShipments") or [{}])[0]
    awb = shipment.get("masterTrackingNumber") or ""
    pieces = shipment.get("pieceResponses") or []
    labels = [Label(f"FEDEX-{p.get('trackingNumber')}.pdf", base64.b64decode(doc["encodedLabel"]))
              for p in pieces for doc in p.get("packageDocuments") or [] if doc.get("encodedLabel")]
    labels += [Label(f"COMMER-INV-{reference}-{awb}.pdf", base64.b64decode(doc["encodedLabel"]))
               for doc in shipment.get("shipmentDocuments") or [] if doc.get("encodedLabel")]
    rating = ((shipment.get("completedShipmentDetail") or {}).get("shipmentRating") or {})
    rate = (rating.get("shipmentRateDetails") or [{}])[0]
    return BookingResult(
        awb=awb,
        package_ids=[p.get("trackingNumber") for p in pieces],
        labels=labels,
        cost=float(rate["totalNetCharge"]) if rate.get("totalNetCharge") is not None else None,
        currency=rate.get("currency") or "",
        raw={"masterTrackingNumber": awb, "serviceType": shipment.get("serviceType")},
    )


def parse_tracking(awb: str, item: dict, resolve, tz: str) -> TrackingResult:
    """One `trackResults[0]` of a trackingnumbers reply. Times go to the system time zone."""
    error = (item or {}).get("error")
    if not item or (error and error.get("code") in NOT_FOUND_CODES) or not item.get("latestStatusDetail"):
        return TrackingResult(awb=awb, status=st.NO_INFORMATION, found=False)
    latest = item["latestStatusDetail"]
    code = latest.get("code") or latest.get("derivedCode") or ""
    status = resolve(code, latest.get("description") or "") or st.IN_TRANSIT
    dates = {d.get("type"): to_local(d.get("dateTime"), tz) for d in item.get("dateAndTimes") or []}
    scans = sorted((scan(e, tz) for e in item.get("scanEvents") or [] if e.get("date")), key=lambda s: s.time)
    estimated = dates.get("ESTIMATED_DELIVERY") or to_local(
        (((item.get("estimatedDeliveryTimeWindow") or {}).get("window") or {}).get("ends")), tz)
    delivered = dates.get("ACTUAL_DELIVERY") if status == st.DELIVERED else None
    return TrackingResult(
        awb=awb,
        status=status,
        status_code=code[:20],
        pickup_date=dates.get("ACTUAL_PICKUP") or dates.get("ACTUAL_TENDER"),
        expected_delivery_date=estimated.date() if estimated else None,
        delivery_date_time=delivered or (scans[-1].time if status == st.DELIVERED and scans else None),
        recipient=((item.get("deliveryDetails") or {}).get("receivedByName") or "")[:140],
        destination=place(((item.get("recipientInformation") or {}).get("address")) or {})[:140],
        scans=scans,
        pod_available=any(i.get("type") == "SIGNATURE_PROOF_OF_DELIVERY" for i in item.get("availableImages") or []),
    )


def track_body(awbs: List[str]) -> dict:
    return {"includeDetailedScans": True,
            "trackingInfo": [{"trackingNumberInfo": {"trackingNumber": awb}} for awb in awbs]}


def track_items(reply: dict) -> Dict[str, dict]:
    """{awb: trackResults[0]} of a trackingnumbers reply."""
    items = {}
    for row in (reply.get("output") or {}).get("completeTrackResults") or []:
        results = row.get("trackResults") or [{}]
        items[row.get("trackingNumber") or ""] = results[0]
    return items


def pod_body(awb: str) -> dict:
    return {"trackDocumentDetail": {"documentType": "SIGNATURE_PROOF_OF_DELIVERY", "documentFormat": "PDF"},
            "trackDocumentSpecification": [{"trackingNumberInfo": {"trackingNumber": awb}}]}


def parse_pod(awb: str, reply: dict) -> Optional[Label]:
    documents = (reply.get("output") or {}).get("documents") or []
    return Label(f"POD-{awb}.pdf", base64.b64decode(documents[0])) if documents else None


def cancel_body(awb: str, account_number: str) -> dict:
    return {"accountNumber": {"value": account_number}, "trackingNumber": awb,
            "deletionControl": "DELETE_ALL_PACKAGES", "emailShipment": False}


def address_body(address: Address) -> dict:
    return {"addressesToValidate": [{"address": party(address)["address"]}]}


def parse_address(reply: dict) -> str:
    rows = (reply.get("output") or {}).get("resolvedAddresses") or []
    if not rows:
        return "FedEx could not resolve the address."
    row = rows[0]
    lines = ", ".join(filter(None, row.get("streetLinesToken") or []))
    where = " ".join(filter(None, (row.get("city"), row.get("stateOrProvinceCode"), row.get("postalCode"),
                                   row.get("countryCode"))))
    return f"FedEx address: {lines} {where}. Classification: {row.get('classification') or 'UNKNOWN'}".strip()


def transit_body(origin: Address, destination: Address, ship_date: date) -> dict:
    return {"requestedShipment": {"shipper": {"address": party(origin)["address"]},
                                  "recipients": [{"address": party(destination)["address"]}],
                                  "shipDateStamp": ship_date.isoformat(), "packagingType": "YOUR_PACKAGING",
                                  "pickupType": "USE_SCHEDULED_PICKUP",
                                  "requestedPackageLineItems": [{"weight": {"units": "KG", "value": 1}}],
                                  # FedEx needs customs data for an international check: one sample line
                                  "customsClearanceDetail": {"commodities": [{
                                      "description": "Cutting Tools", "quantity": 1, "quantityUnits": "PCS", "numberOfPieces": 1,
                                      "weight": {"units": "KG", "value": 1},
                                      "customsValue": {"amount": 100, "currency": "USD"}}]}},
            "carrierCodes": ["FDXE"]}


def parse_transit(reply: dict) -> List[str]:
    """One line for each service: name and the committed delivery day."""
    lines = []
    for row in (reply.get("output") or {}).get("transitTimes") or []:
        for option in row.get("transitTimeDetails") or []:
            when = ((option.get("commit") or {}).get("dateDetail") or {})
            day = " ".join(filter(None, (when.get("dayOfWeek"), when.get("day"), when.get("time"))))
            lines.append(f"{option.get('serviceName') or option.get('serviceType')}: {day or 'no commit date'}")
    return lines


# ----------------------------------------------------------------------------- parts of a body


def shipment_base(req: ShipmentRequest, account_number: str) -> dict:
    return {
        "serviceType": req.service_code,
        "packagingType": "YOUR_PACKAGING",
        "pickupType": "USE_SCHEDULED_PICKUP",
        "totalPackageCount": len(req.packages),
        "requestedPackageLineItems": package_lines(req),
        "customsClearanceDetail": customs(req, account_number),
    }


def party(address: Address) -> dict:
    """Contact, address and TIN of a FedEx shipper or recipient. The limits are FedEx's."""
    contact = {"personName": (address.contact or address.name)[:35], "companyName": address.company[:35],
               "phoneNumber": re.sub(r"[^0-9+]", "", address.phone)[:15]}
    if address.email:
        contact["emailAddress"] = address.email[:80]
    result = {
        "contact": contact,
        "address": {
            "streetLines": [line[:35] for line in (address.line1, address.line2) if line],
            "city": address.city[:35],
            "stateOrProvinceCode": address.state_code.strip()[:2],
            "postalCode": address.pincode[:10],
            "countryCode": address.country_code,
            "residential": bool(address.is_residential),
        },
    }
    if (address.tax_id or "").strip().upper() not in NO_TIN:
        result["tins"] = [{"number": address.tax_id.strip(), "tinType": "BUSINESS_NATIONAL"}]
    return result


def package_lines(req: ShipmentRequest) -> List[dict]:
    lines = []
    for n, pkg in enumerate(req.packages, start=1):
        line = {"sequenceNumber": n, "groupPackageCount": 1, "weight": {"units": "KG", "value": round(pkg.weight, 2)}}
        if pkg.length and pkg.width and pkg.height:
            line["dimensions"] = {"length": round(pkg.length), "width": round(pkg.width), "height": round(pkg.height),
                                  "units": "CM"}
        lines.append(line)
    return lines


def customs(req: ShipmentRequest, account_number: str) -> dict:
    """The SOAP code sent customs data on every shipment; FedEx India needs it for domestic too."""
    commodities = customs_lines(req)
    total = round(sum(c["customsValue"]["amount"] for c in commodities), 2)
    return {
        "dutiesPayment": payment(req.duties_payment_by or "RECIPIENT", account_number),
        "isDocumentOnly": False,
        "commercialInvoice": {"shipmentPurpose": req.purpose or "SOLD"},
        "commodities": commodities,
        "totalCustomsValue": {"amount": total, "currency": req.currency},
    }


def customs_lines(req: ShipmentRequest) -> List[dict]:
    """One line per invoice item for a sale. Other purposes get one line of value 1, and a
    shipment with no items gets one printed-matter line (both as the SOAP code did)."""
    weight = round(sum(p.weight for p in req.packages), 2)
    items = req.commodities
    if not items:
        return [commodity(Commodity(PRINTED_MATTER[0], len(req.packages) or 1, "PCS", req.declared_value / (len(req.packages) or 1),
                                    weight, PRINTED_MATTER[1], req.origin.country_code or "IN"), req.currency)]
    if (req.purpose or "SOLD") != "SOLD":
        qty = sum(i.quantity for i in items) or 1
        first = items[0]
        return [commodity(Commodity(first.description, qty, "PCS", 1 / qty, weight, first.hs_code,
                                    first.country_of_manufacture), req.currency)]
    return [commodity(item, req.currency) for item in spread_weight(items, weight)]


def commodity(item: Commodity, currency: str) -> dict:
    value = round(item.unit_price * item.quantity, 2)
    line = {
        "description": item.description[:450],
        "countryOfManufacture": item.country_of_manufacture or "IN",
        "quantity": int(round(item.quantity)) or 1,
        "quantityUnits": "PCS",
        "numberOfPieces": 1,
        "unitPrice": {"amount": round(item.unit_price, 4), "currency": currency},
        "customsValue": {"amount": value, "currency": currency},
        "weight": {"units": "KG", "value": round(max(item.weight, 0.01), 2)},
    }
    if item.hs_code:
        line["harmonizedCode"] = re.sub(r"\D", "", item.hs_code)[:8]
    return line


def spread_weight(items: List[Commodity], total: float) -> List[Commodity]:
    """FedEx needs a weight on each line. Items with no weight share the rest by quantity."""
    known = sum(i.weight for i in items if i.weight > 0)
    empty = [i for i in items if i.weight <= 0]
    qty = sum(i.quantity for i in empty) or 1
    rest = max(total - known, 0)
    return [i if i.weight > 0 else Commodity(i.description, i.quantity, i.quantity_uom, i.unit_price,
                                             round(rest * i.quantity / qty, 3), i.hs_code, i.country_of_manufacture)
            for i in items]


def customer_references(req: ShipmentRequest) -> List[dict]:
    refs = [{"customerReferenceType": "CUSTOMER_REFERENCE", "value": "-".join(req.references)[:40]}]
    po = re.sub(r"[^a-zA-Z0-9]", "", req.purchase_order or "")[:16]
    if po:
        refs.append({"customerReferenceType": "P_O_NUMBER", "value": po})
    if req.invoice_number:
        refs.append({"customerReferenceType": "INVOICE_NUMBER", "value": req.invoice_number[:30]})
    return refs


def needs_commercial_invoice(req: ShipmentRequest) -> bool:
    international = req.origin.country_code != req.destination.country_code
    return international and (req.purpose or "SOLD") == "SOLD" and bool(req.invoice_number)


def payment(payment_type: str, account_number: str) -> dict:
    result = {"paymentType": payment_type}
    if payment_type == "SENDER":
        result["payor"] = {"responsibleParty": {"accountNumber": {"value": account_number}}}
    return result


# ----------------------------------------------------------------------------- reply helpers


def transit_days(detail: dict) -> Optional[int]:
    words = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9,
             "TEN": 10}
    value = ((detail.get("operationalDetail") or {}).get("transitTime")
             or ((detail.get("commit") or {}).get("transitDays") or {}).get("minimumTransitTime") or "")
    return words.get(str(value).replace("_DAYS", "").replace("_DAY", "").upper())


def delivery_date(detail: dict) -> Optional[date]:
    value = (detail.get("operationalDetail") or {}).get("deliveryDate") or \
        (((detail.get("commit") or {}).get("dateDetail") or {}).get("dayFormat"))
    try:
        return datetime.fromisoformat(value).date() if value else None
    except ValueError:
        return None


def scan(event: dict, tz: str) -> Scan:
    where = place(event.get("scanLocation") or {}, postal=True) or "Base Location"
    text = event.get("eventDescription") or ""
    if event.get("exceptionCode"):
        text += f" Excep Code: {event['exceptionCode']} {event.get('exceptionDescription') or ''}"
    return Scan(time=to_local(event["date"], tz), location=where[:140],
                status_detail=f"{event.get('eventType') or ''}: {text}".strip()[:140])


def place(address: dict, postal: bool = False) -> str:
    keys = ("city", "stateOrProvinceCode", "postalCode", "countryName") if postal else \
        ("city", "stateOrProvinceCode", "countryName")
    return ", ".join(str(address[k]).strip() for k in keys if address.get(k))


def to_local(value: Optional[str], tz: str) -> Optional[datetime]:
    """'2026-10-16T11:47:00-04:00' -> naive datetime in `tz`. A value with no offset is kept."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(pytz.timezone(tz)).replace(tzinfo=None)
