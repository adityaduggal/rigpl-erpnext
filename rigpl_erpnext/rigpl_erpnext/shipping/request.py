"""
Builds a ShipmentRequest from a Carrier Tracking (#168), so the adapters never read docs.
About 6 queries for any number of packages and items.
"""
from typing import Dict, List, Optional

import frappe
from frappe.query_builder.functions import Coalesce
from frappe.utils import flt, getdate, nowdate

from ...utils.batch_write_utils import bulk_set_values
from . import status as st
from .base import Address, Commodity, Package, ShipmentRequest, TradeDocument

ADDRESS_FIELDS = ["name", "address_title", "address_line1", "address_line2", "city", "state", "state_rigpl",
                  "pincode", "country", "phone", "email_id", "gstin"]


def load_addresses(names: List[str], contact_name: str = "", contact_address: str = "") -> Dict[str, Address]:
    """The Contact (the receiver's person) is used only for `contact_address`, so the
    shipper never gets the customer's name or phone."""
    rows = frappe.get_all("Address", filters={"name": ["in", [n for n in names if n]]}, fields=ADDRESS_FIELDS)
    codes = codes_by_name("Country", "code", {r.country for r in rows})
    states = codes_by_name("State", "state_code", {r.state_rigpl for r in rows})
    person_row = frappe.db.get_value("Contact", contact_name, ["first_name", "last_name", "mobile_no", "phone", "email_id"],
                                     as_dict=True) if contact_name else None
    result = {}
    for row in rows:
        contact = person_row if row.name == contact_address else None
        person = " ".join(filter(None, (contact.first_name, contact.last_name))) if contact else ""
        result[row.name] = Address(
            name=row.address_title or row.name,
            line1=row.address_line1 or "",
            line2=row.address_line2 or "",
            city=row.city or "",
            state=row.state or "",
            state_code=(states.get(row.state_rigpl) or "").strip(),
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


def codes_by_name(doctype: str, field: str, names) -> Dict[str, str]:
    """{name: field} for the non-empty names. No query when there are none."""
    names = [n for n in names if n]
    if not names:
        return {}
    return dict(frappe.get_all(doctype, filters={"name": ["in", names]}, fields=["name", field], as_list=True))


def load_commodities(doc) -> List[Commodity]:
    """The Sales Invoice items, for export paperwork (FedEx). 4 queries."""
    if doc.document != "Sales Invoice" or not doc.document_name:
        return []
    items = frappe.get_all("Sales Invoice Item", filters={"parent": doc.document_name, "parenttype": "Sales Invoice"},
                           fields=["item_code", "item_name", "qty", "uom", "rate", "gst_hsn_code", "total_weight"],
                           order_by="idx")
    origin = codes_by_name("Item", "country_of_origin", {i.item_code for i in items})
    codes = codes_by_name("Country", "code", set(origin.values()))
    # Customs text is the HSN description, as the SOAP code did: item names are internal codes
    hsn = codes_by_name("GST HSN Code", "description", {i.gst_hsn_code for i in items})
    return [Commodity(description=(hsn.get(i.gst_hsn_code) or i.item_name or i.item_code)[:100], quantity=flt(i.qty),
                      quantity_uom=i.uom or "EA",
                      unit_price=flt(i.rate), weight=flt(i.total_weight), hs_code=i.gst_hsn_code or "",
                      country_of_manufacture=(codes.get(origin.get(i.item_code)) or "IN").upper())
            for i in items]


def build_shipment_request(doc, service_code: str, test_marking: bool = False) -> ShipmentRequest:
    addresses = load_addresses([doc.from_address, doc.to_address], doc.contact_person, doc.to_address)
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
        purchase_order=purchase_order(doc),
        purpose=doc.purpose or "SOLD",
        is_inward=bool(doc.is_inward),
        duties_payment_by=doc.duties_payment_by or "RECIPIENT",
        description=(doc.shipment_notes or "Cutting Tools")[:100],
        commodities=load_commodities(doc),
        ship_date=getdate(nowdate()),
        test_marking=test_marking,
    )


def purchase_order(doc) -> str:
    """The customer PO of a Sales Invoice, or the Purchase Order name."""
    if doc.document == "Purchase Order":
        return doc.document_name or ""
    if doc.document == "Sales Invoice" and doc.document_name:
        return frappe.db.get_value("Sales Invoice", doc.document_name, "po_no") or ""
    return ""


# ----------------------------------------------------------------------------- trade documents (#240)

DOCUMENT_FIELDS = ("customs_invoice", "other_trade_document")
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024  # the FedEx limit for one document
# The file types that the FedEx document upload takes, by extension
CONTENT_TYPES = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                 "txt": "text/plain", "doc": "application/msword", "xls": "application/vnd.ms-excel",
                 "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def trade_documents(doc) -> List[TradeDocument]:
    """The customs documents of an export booking. The invoice is a tax invoice for a sale, and a
    pro forma invoice for all other purposes (FedEx: SOLD is not valid with a pro forma invoice)."""
    if not doc.customs_invoice:
        frappe.throw(f"Attach the invoice PDF in Customs Invoice PDF before you book export {doc.name}. "
                     "FedEx sends it to customs electronically.", title="Customs Invoice Needed")
    invoice_type = "COMMERCIAL_INVOICE" if (doc.purpose or "SOLD") == "SOLD" else "PRO_FORMA_INVOICE"
    documents = [trade_document(doc, "customs_invoice", invoice_type, pdf_only=True)]
    if doc.other_trade_document:
        documents.append(trade_document(doc, "other_trade_document", "OTHER", pdf_only=False))
    return documents


def trade_document(doc, fieldname: str, doc_type: str, pdf_only: bool) -> TradeDocument:
    label = doc.meta.get_label(fieldname)
    url = doc.get(fieldname)
    name = frappe.db.get_value("File", {"file_url": url, "attached_to_doctype": doc.doctype,
                                        "attached_to_name": doc.name}, "name")
    if not name:
        frappe.throw(f"{label}: attach the file again. {url} is not a file of {doc.name}.")
    file_doc = frappe.get_doc("File", name)
    extension = (file_doc.file_name or url).rsplit(".", 1)[-1].lower()
    content = file_doc.get_content()
    content = content.encode() if isinstance(content, str) else content
    if pdf_only and (extension != "pdf" or not content.startswith(b"%PDF")):
        frappe.throw(f"{label} must be a PDF file.")
    if extension not in CONTENT_TYPES:
        frappe.throw(f"{label}: FedEx does not take .{extension} files. Use PDF, an image, Word or Excel.")
    if len(content) > MAX_DOCUMENT_BYTES:
        frappe.throw(f"{label} is {len(content) / 1024 / 1024:.1f} MB. FedEx takes at most 5 MB.")
    return TradeDocument(doc_type, file_doc.file_name, content, CONTENT_TYPES[extension])


# ----------------------------------------------------------------------------- courier export clearance (#241)

CSB_IV, CSB_V, SHIPPING_BILL = "CSB-IV", "CSB-V", "Shipping Bill"
CSB_V_LIMIT = 1000000  # Rs 10 lakh: the most one CSB-V consignment may be worth (Courier Regulations 2010)
TEMPLATE_FIELDS = ["iec_code", "bank_ad_code", "export_type", "lut_no_and_date"]


def export_clearance(purpose: str, base_value: Optional[float]) -> str:
    """CSB-V for a sale up to Rs 10 lakh, a Shipping Bill (formal clearance) above it, CSB-IV
    for samples, gifts and other goods that are not sold. Empty for a sale with no value."""
    if (purpose or "SOLD") != "SOLD":
        return CSB_IV
    if base_value is None:
        return ""
    return CSB_V if flt(base_value) <= CSB_V_LIMIT else SHIPPING_BILL


def invoice_base_value(doc) -> Optional[float]:
    """The invoice value in INR, the value that customs uses for the CSB-V limit."""
    if doc.document != "Sales Invoice" or not doc.document_name:
        return None
    return flt(frappe.db.get_value("Sales Invoice", doc.document_name, "base_grand_total"))


def export_instructions(doc, req: ShipmentRequest) -> str:
    """The clearance line for the carrier. A sale needs the IEC, AD code and export type of the
    Sales Invoice tax template, and the GSTIN of the From Address."""
    clearance = doc.export_clearance or export_clearance(doc.purpose, invoice_base_value(doc))
    if clearance == CSB_IV:
        return clearance_line(clearance, frappe._dict(), req.origin.tax_id, doc.purpose)
    template_name = frappe.db.get_value("Sales Invoice", doc.document_name, "taxes_and_charges") \
        if doc.document == "Sales Invoice" and doc.document_name else ""
    template = frappe.db.get_value("Sales Taxes and Charges Template", template_name, TEMPLATE_FIELDS,
                                   as_dict=True) if template_name else None
    template = template or frappe._dict()
    missing = [label for label, value in (("IEC Code", template.iec_code), ("Bank AD Code", template.bank_ad_code),
                                          ("Export Type", template.export_type)) if not value]
    if not tin(req.origin.tax_id):
        missing.append(f"GSTIN of From Address {doc.from_address}")
    if missing:
        where = frappe.get_desk_link("Sales Taxes and Charges Template", template_name) if template_name \
            else f"the Sales Invoice {doc.document_name or ''}".strip()
        frappe.throw(f"Export {doc.name} ({clearance or CSB_V}) needs {', '.join(missing)}. Set them in {where}.",
                     title="Export Details Needed")
    return clearance_line(clearance, template, req.origin.tax_id, doc.purpose)


def clearance_line(clearance: str, template, gstin: str, purpose: str) -> str:
    """For example: 'CSB-V. IEC 0500000001. AD Code 0123456. GSTIN 06AAA. Export under LUT ... without IGST.'"""
    if clearance == CSB_IV:
        parts = [f"CSB-IV. {(purpose or '').replace('_', ' ').title()}, not for sale"]
    elif clearance == SHIPPING_BILL:
        parts = ["Shipping Bill. Value above Rs 10 lakh, formal clearance"]
    else:
        parts = [CSB_V]
    if template.get("iec_code"):
        parts.append(f"IEC {template.get('iec_code')}")
    if template.get("bank_ad_code"):
        parts.append(f"AD Code {template.get('bank_ad_code')}")
    if tin(gstin):
        parts.append(f"GSTIN {gstin.strip()}")
    if template.get("export_type") == "Without Payment of Tax":
        lut = tin(template.get("lut_no_and_date") or "")
        parts.append(f"Export under LUT {lut} without IGST" if lut else "Export under LUT without IGST")
    elif template.get("export_type") == "With Payment of Tax":
        parts.append("Export with payment of IGST")
    return ". ".join(parts) + "."


def tin(value: str) -> str:
    """The value, or empty for the NA that marks an empty GSTIN or LUT."""
    value = (value or "").strip()
    return "" if value.upper() in ("", "NA") else value


def delete_delivered_documents(limit: int = 500) -> int:
    """Daily: deletes the trade documents of delivered trackings. Customs has them by then.
    The File delete runs per file, because its hook removes the file from the disk."""
    ct = frappe.qb.DocType("Carrier Tracking")
    rows = (frappe.qb.from_(ct).select(ct.name, *(ct[f] for f in DOCUMENT_FIELDS))
            .where(ct.status == st.DELIVERED)
            .where((Coalesce(ct.customs_invoice, "") != "") | (Coalesce(ct.other_trade_document, "") != ""))
            .limit(limit)).run(as_dict=True)
    if not rows:
        return 0
    urls = {(r.name, r[f]) for r in rows for f in DOCUMENT_FIELDS if r[f]}
    files = frappe.get_all("File", filters={"attached_to_doctype": "Carrier Tracking",
                                            "attached_to_name": ["in", [r.name for r in rows]],
                                            "file_url": ["in", list({url for _, url in urls})]},
                           fields=["name", "attached_to_name", "file_url"])
    for f in files:
        if (f.attached_to_name, f.file_url) in urls:
            frappe.delete_doc("File", f.name, ignore_permissions=True)
    for fieldname in DOCUMENT_FIELDS:
        bulk_set_values("Carrier Tracking", fieldname, {r.name: "" for r in rows if r[fieldname]},
                        {r.name: r[fieldname] for r in rows if r[fieldname]})
    return len(rows)
