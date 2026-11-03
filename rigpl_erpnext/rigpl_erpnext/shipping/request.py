"""
Builds a ShipmentRequest from a Carrier Tracking (#168), so the adapters never read docs.
About 6 queries for any number of packages and items.
"""
from typing import Dict, List

import frappe
from frappe.utils import flt, getdate, nowdate

from .base import Address, Commodity, Package, ShipmentRequest

ADDRESS_FIELDS = ["name", "address_title", "address_line1", "address_line2", "city", "state", "gst_state_number",
                  "pincode", "country", "phone", "email_id", "gstin"]


def load_addresses(names: List[str], contact_name: str = "") -> Dict[str, Address]:
    rows = frappe.get_all("Address", filters={"name": ["in", [n for n in names if n]]}, fields=ADDRESS_FIELDS)
    codes = dict(frappe.get_all("Country", filters={"name": ["in", list({r.country for r in rows if r.country})]},
                                fields=["name", "code"], as_list=True))
    contact = frappe.db.get_value("Contact", contact_name, ["first_name", "last_name", "mobile_no", "phone", "email_id"],
                                  as_dict=True) if contact_name else None
    result = {}
    for row in rows:
        person = " ".join(filter(None, (contact.first_name, contact.last_name))) if contact else ""
        result[row.name] = Address(
            name=row.address_title or row.name,
            line1=row.address_line1 or "",
            line2=row.address_line2 or "",
            city=row.city or "",
            state=row.state or "",
            state_code=row.gst_state_number or "",
            pincode=(row.pincode or "").replace(" ", ""),
            country=row.country or "",
            country_code=(codes.get(row.country) or "").upper(),
            phone=row.phone or (contact and (contact.mobile_no or contact.phone)) or "",
            email=row.email_id or (contact and contact.email_id) or "",
            contact=person or row.address_title or "",
            company=row.address_title or "",
            tax_id=row.gstin or "",
        )
    return result


def load_packages(doc) -> List[Package]:
    rows = doc.get("shipment_package_details") or []
    dims = {r.name: r for r in frappe.get_all(
        "Shipment Package", filters={"name": ["in", list({r.shipment_package for r in rows if r.shipment_package})]},
        fields=["name", "length", "width", "height"])}
    packages = []
    for row in rows:
        size = dims.get(row.shipment_package) or frappe._dict()
        packages.append(Package(weight=flt(row.package_weight), length=flt(size.length), width=flt(size.width),
                                height=flt(size.height), declared_value=flt(doc.amount)))
    return packages


def load_commodities(doc) -> List[Commodity]:
    """The Sales Invoice items, for export paperwork (FedEx). 2 queries."""
    if doc.document != "Sales Invoice" or not doc.document_name:
        return []
    items = frappe.get_all("Sales Invoice Item", filters={"parent": doc.document_name, "parenttype": "Sales Invoice"},
                           fields=["item_code", "item_name", "qty", "uom", "rate", "gst_hsn_code", "total_weight"],
                           order_by="idx")
    return [Commodity(description=(i.item_name or i.item_code)[:100], quantity=flt(i.qty), quantity_uom=i.uom or "EA",
                      unit_price=flt(i.rate), weight=flt(i.total_weight), hs_code=i.gst_hsn_code or "")
            for i in items]


def build_shipment_request(doc, service_code: str, test_marking: bool = False) -> ShipmentRequest:
    addresses = load_addresses([doc.from_address, doc.to_address], doc.contact_person)
    if doc.from_address not in addresses or doc.to_address not in addresses:
        frappe.throw(f"From Address and To Address are needed in {frappe.get_desk_link(doc.doctype, doc.name)}")
    return ShipmentRequest(
        reference=doc.name,
        service_code=service_code,
        origin=addresses[doc.from_address],
        destination=addresses[doc.to_address],
        packages=load_packages(doc),
        declared_value=flt(doc.amount),
        currency=doc.currency or "INR",
        invoice_number=doc.document_name if doc.document == "Sales Invoice" else "",
        purchase_order=doc.document_name if doc.document == "Purchase Order" else "",
        purpose=doc.purpose or "SOLD",
        is_inward=bool(doc.is_inward),
        duties_payment_by=doc.duties_payment_by or "RECIPIENT",
        description=(doc.shipment_notes or "Cutting Tools")[:100],
        commodities=load_commodities(doc),
        ship_date=getdate(nowdate()),
        test_marking=test_marking,
    )
