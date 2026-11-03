# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
"""
Carrier Tracking. The carrier APIs are in `rigpl_erpnext/shipping/` (#168): the buttons call
`shipping.actions`, and the jobs in `shipping.tracking` write the tracking data.
"""
import frappe
from frappe.utils import flt
from frappe.website.website_generator import WebsiteGenerator
from rohit_common.utils.rohit_common_utils import get_email_id

from ...shipping import access, actions
from ...shipping.accounts import BOOKING
from ...shipping.registry import get_carrier, transporter_api
from ...shipping.tracking import track_now
from ...shipping.validations import courier_charges_validation
from ....utils.sales_utils import validate_address_google_update


class CarrierTracking(WebsiteGenerator):
    allowed_docs_items = ["Sales Invoice", "Purchase Order"]
    # Each view is checked for the viewer (#83), so the page is never cached. The DocType has
    # allow_guest_to_view = 0: in v13 that flag puts every route in sitemap.xml and lets guests
    # list the documents (www/list.py). The page itself still renders for guests.
    website = frappe._dict(no_cache=1, sitemap=0)

    # ------------------------------------------------------------------ buttons (whitelisted for v13)

    @frappe.whitelist()
    def get_status(self):
        track_now(self)
        self.reload()

    @frappe.whitelist()
    def pushdata(self):
        carrier = get_carrier(self.carrier_name)
        if not carrier or not carrier.provider.supports("push"):
            frappe.throw(f"{frappe.get_desk_link('Transporters', self.carrier_name)} is not tracked on Shipway")
        if self.posted_to_shipway:
            frappe.msgprint("Already Posted to Shipway")
            return
        if carrier.provider.push(self.name, self.awb_number, carrier.service_code):
            frappe.db.set_value(self.doctype, self.name, {"posted_to_shipway": 1, "status": "Shipment Data Uploaded"})
        else:
            frappe.msgprint(f"Some Issues in posting {self.name}")

    @frappe.whitelist()
    def get_rates(self):
        self.validate()
        if not self.shipment_package_details:
            frappe.throw(f"Shipment Package Details are needed for the rates of {self.name}")
        actions.get_rates(self)
        self.save()

    @frappe.whitelist()
    def book_shipment(self, test_marking=0):
        self.validate()
        actions.book(self, test_marking=bool(int(test_marking or 0)))

    @frappe.whitelist()
    def get_labels(self):
        actions.get_labels(self)

    @frappe.whitelist()
    def get_pod(self):
        actions.get_pod(self)

    @frappe.whitelist()
    def available_services(self):
        frappe.msgprint(actions.check_serviceability(self))

    @frappe.whitelist()
    def address_validation(self):
        actions.validate_address(self)

    @frappe.whitelist()
    def delete_shipment(self):
        actions.cancel(self)

    # ------------------------------------------------------------------------------- lifecycle

    def validate(self):
        tpt = frappe.get_cached_doc("Transporters", self.carrier_name)
        provider, api_mode = transporter_api(self.carrier_name)
        if self.reference_document_name and \
                self.reference_document_name.split("-")[0] != (self.document_name or "").split("-")[0]:
            frappe.throw(f"{self.name} is Already Linked to {self.document}# {self.reference_document_name}")
        self.update_fields(tpt)
        if self.to_address:
            validate_address_google_update(self.to_address)
        if self.from_address:
            validate_address_google_update(self.from_address)
        if self.docstatus != 1:
            self.published = 0
        if not self.published:
            self.route = ""
        elif access.needs_new_route(self.name, self.route):
            self.route = access.new_route()
        from_address = frappe.get_doc("Address", self.from_address)
        to_address = frappe.get_doc("Address", self.to_address)
        self.check_invoice_integrity(from_address)
        self.set_recipient_email(to_address)
        # The old code ran these checks only for FedEx booking (fedex_credentials), keep that
        if api_mode == BOOKING and provider == "FedEx":
            self.fedex_account_number = frappe.get_cached_value(
                "Shipping Provider Account", tpt.shipping_provider_account, "account_number")
            self.sales_invoice_validations()
            self.ctrack_validations()
            courier_charges_validation(self, tpt.max_percent_of_invoice_value)
            self.carrier_validations(tpt, from_address, to_address)
        elif tpt.is_domestic_only and from_address.country != to_address.country:
            frappe.throw(f"For {frappe.get_desk_link(self.doctype, self.name)} "
                         f"{frappe.get_desk_link('Transporters', self.carrier_name)} is Only for Domestic Booking")

    def on_submit(self):
        route = access.new_route() if access.needs_new_route(self.name, self.route) else self.route
        self.db_set({"published": 1, "route": route})
        self.push_data_to_sales_invoice()

    def get_context(self, context):
        """The web page (#83): only for a signed link or a linked user, until it expires."""
        context.no_cache = 1
        context.sitemap = 0
        context.title = context.page_title = "Shipment Tracking"
        context.metatags = {"robots": "noindex,nofollow"}
        if access.can_view(self, access.request_args()):
            return
        for key in list(self.as_dict()) + ["docname"]:
            context.pop(key, None)
        context.doc = frappe._dict()
        context.expired = True

    def get_tracking_url(self) -> str:
        """The signed link for the shipment email (Notification: {{ doc.get_tracking_url() }})."""
        return access.signed_url(self) if self.published and self.route else ""

    def on_cancel(self):
        self.db_set({"published": 0, "route": ""})

    def push_data_to_sales_invoice(self):
        if self.document == "Sales Invoice":
            frappe.db.set_value("Sales Invoice", self.document_name,
                                {"transporters": self.carrier_name, "lr_no": self.awb_number})

    # ------------------------------------------------------------------------------ validations

    def update_fields(self, tpt):
        if self.document == "Sales Invoice":
            si_doc = frappe.get_doc("Sales Invoice", self.document_name)
            self.receiver_document = "Customer"
            self.receiver_name = si_doc.customer
            tax = frappe.get_cached_value("Sales Taxes and Charges Template", si_doc.taxes_and_charges,
                                          ["from_address", "is_sample"], as_dict=True) or frappe._dict()
            self.set_from_address(tax.from_address, si_doc.taxes_and_charges)
            self.to_address = si_doc.shipping_address_name
            self.contact_person = si_doc.contact_person
            if tax.is_sample == 1:
                self.purpose = "SAMPLE"
                if not self.amount:
                    self.amount = 1
            else:
                self.purpose = "SOLD"
                self.amount = si_doc.grand_total
            self.currency = si_doc.currency
            self.courier_charged = sum(flt(d.base_amount) for d in si_doc.items
                                       if d.income_account == tpt.invoice_courier_charges_account)
        elif self.document == "Purchase Order":
            po_doc = frappe.get_doc("Purchase Order", self.document_name)
            self.receiver_document = "Supplier"
            self.receiver_name = po_doc.supplier
            from_address = frappe.get_cached_value("Purchase Taxes and Charges Template", po_doc.taxes_and_charges,
                                                   "from_address")
            self.set_from_address(from_address, po_doc.taxes_and_charges)
            self.to_address = po_doc.supplier_address
            self.contact_person = po_doc.contact_person
            self.purpose = "NOT_SOLD"
            self.amount = po_doc.grand_total
            self.currency = po_doc.currency
        elif self.document in ("Customer", "Supplier", "Company", "Sales Partner", "Employee"):
            self.update_fields_for_party()

    def set_from_address(self, template_address, template):
        if self.from_address:
            return
        if not self.get("__islocal"):
            frappe.throw("From Address is Needed before Saving the Document")
        if not template_address:
            frappe.throw(f"Update From Address in Tax Template {template}")
        self.from_address = template_address

    def update_fields_for_party(self):
        for field, message in (("carrier_name", "Select the Carrier Through which Shipment is to be Sent"),
                               ("purpose", "Select the Purpose of Shipment"),
                               ("from_address", "Select the Address from which Shipment is to be Sent"),
                               ("shipment_notes", "Add a Small description of the Type of Things in Consignment in "
                                                  "Shipment Notes")):
            if not self.get(field):
                frappe.throw(message)
        self.receiver_document = self.document
        self.receiver_name = self.document_name
        linked = self.get_party_links()
        if not self.to_address:
            self.to_address = next(iter(linked["Address"]), None)
        if not self.contact_person:
            self.contact_person = next(iter(linked["Contact"]), None)
        if self.to_address not in linked["Address"]:
            frappe.throw(f"To Address: {self.to_address} not from {self.document}: {self.document_name}")
        if self.contact_person and self.contact_person not in linked["Contact"]:
            frappe.throw(f"Contact: {self.contact_person} not from {self.document}: {self.document_name}")
        if not self.amount:
            self.amount = 1
        self.currency = "INR"

    def get_party_links(self):
        """{"Address": [...], "Contact": [...]} linked to the party: 1 query."""
        rows = frappe.get_all("Dynamic Link", filters={"link_doctype": self.document, "link_name": self.document_name,
                                                       "parenttype": ["in", ["Address", "Contact"]]},
                              fields=["parent", "parenttype"], order_by="creation")
        links = {"Address": [], "Contact": []}
        for row in rows:
            links[row.parenttype].append(row.parent)
        return links

    def check_invoice_integrity(self, from_address):
        if from_address.pincode is None:
            frappe.throw(f"No Pin Code Defined for Address {self.from_address} if pincode not known enter NA")
        if self.document == "Sales Invoice":
            si = frappe.db.get_value("Sales Invoice", self.document_name, ["transporters", "lr_no"], as_dict=True)
            self.invoice_integrity = int(bool(si) and self.carrier_name == si.transporters
                                         and self.awb_number == si.lr_no)

    def carrier_validations(self, tpt, from_address, to_address):
        name = self.carrier_name
        own_from, own_to = from_address.is_your_company_address == 1, to_address.is_your_company_address == 1
        same_country = from_address.country == to_address.country
        if tpt.is_outward_only == 1:
            if self.is_inward != 1 and not own_from:
                frappe.throw(f"Since {name} is Outward Transporter, From Address Should be Owned Address")
            if self.is_inward == 1 and own_from:
                frappe.throw(f"Since {name} is Marked For Inward Shipment, From Address Should Not be Owned Address")
        else:
            if own_from:
                frappe.throw(f"Since {name} is Inward Transporter, From Address Should be not be Owned Address")
            if not own_to:
                frappe.throw(f"Since {name} is Inward Transporter, To Address Should be Owned Address")
        if tpt.is_export_only == 1 and same_country:
            frappe.throw(f"Since {name} is Export Transporter, To Address Should be not be in {from_address.country}")
        if tpt.is_imports_only == 1:
            if own_from:
                frappe.throw(f"Since {name} is Import Transporter, From Address Should be not owned Address")
            if same_country:
                frappe.throw(f"Since {name} is Import Transporter, From Address Country Should not be Same as To Address")
        if tpt.is_domestic_only == 1 and not same_country:
            frappe.throw(f"Since {name} is Domestic Transporter, From and To Address Should be in Same Country")
        if flt(tpt.minimum_weight) > 0 and not self.get("__islocal") and flt(tpt.minimum_weight) > flt(self.total_weight):
            frappe.throw(f"Minimum Weight for {name} is {tpt.minimum_weight} kgs")
        if flt(tpt.maximum_amount) > 0 and flt(tpt.maximum_amount) < flt(self.amount):
            frappe.throw(f"Maximum Value for {name} is {tpt.maximum_amount}")
        if flt(self.amount) < 1:
            frappe.throw("Amount Should be One or More than One")

    def ctrack_validations(self):
        # Duties paid by the sender is a risky option, so only a System Manager may change it
        if self.duties_payment_by == "SENDER" and "System Manager" not in frappe.get_roles():
            frappe.throw(f"Only System Managers are Allowed to Make Changes to {self.name} as Duties Payment is by "
                         f"{self.duties_payment_by}")
        packages = {p.name: p for p in frappe.get_all(
            "Shipment Package", filters={"name": ["in", [r.shipment_package for r in self.shipment_package_details]]},
            fields=["name", "title", "volumetric_weight_in_kgs"])}
        for row in self.shipment_package_details:
            pkg = packages.get(row.shipment_package) or frappe._dict()
            row.package_name = pkg.title
            row.volumetric_weight = pkg.volumetric_weight_in_kgs
            if row.weight_uom != "Kg":
                frappe.throw("Only Kg is allowed currently in Package Weight UoM")
            if flt(row.volumetric_weight) > flt(row.package_weight):
                frappe.throw("Parcel Weight Less than Volumetric Weight, USE Smaller Package or Change the "
                             f"Weight in Row {row.idx}")

    def sales_invoice_validations(self):
        if self.document in CarrierTracking.allowed_docs_items:
            others = frappe.get_all("Carrier Tracking", filters={"document": self.document, "document_name": self.document_name,
                                                                 "docstatus": ["!=", 2], "name": ["!=", self.name]},
                                    pluck="name", limit=1)
            if others:
                frappe.throw(f"{self.document}: {self.document_name} is already linked to {others[0]}")
            if self.awb_number and self.document == "Sales Invoice" and \
                    self.awb_number != frappe.db.get_value("Sales Invoice", self.document_name, "lr_no"):
                self.push_data_to_sales_invoice()
        elif self.purpose == "SOLD":
            frappe.throw("Purpose SOLD only possible for Sales Invoices")
        if self.shipment_package_details:
            total_weight = sum(flt(d.package_weight) for d in self.shipment_package_details)
            self.weight_uom = self.shipment_package_details[-1].weight_uom
            self.total_handling_units = len(self.shipment_package_details)
            if total_weight > 0:
                self.total_weight = total_weight

    def set_recipient_email(self, to_address):
        to_add_email = get_email_id(to_address.email_id)
        contact_email = get_email_id(frappe.db.get_value("Contact", self.contact_person, "email_id")) \
            if self.contact_person else ""
        if self.receiver_document == "Customer":
            self.set_sales_person_email()
        emails = [e for e in (to_add_email, contact_email) if e]
        joined = ", ".join(emails)
        if len(joined) < 140:
            self.customer_emails = joined
        else:
            self.customer_emails = next((e for e in reversed(emails) if len(e) < 140), "")
        if not emails:
            frappe.msgprint("No Email in Address or Contact for Customer")

    def set_sales_person_email(self):
        sales_persons = frappe.get_all("Sales Team", filters={"parenttype": "Customer", "parent": self.receiver_name},
                                       pluck="sales_person")
        if not sales_persons:
            return
        employees = dict(frappe.get_all("Sales Person", filters={"name": ["in", sales_persons]},
                                        fields=["name", "employee"], as_list=True))
        for sales_person in sales_persons:
            if not employees.get(sales_person):
                frappe.throw(f"No Employee Linked with Sales Person {sales_person} for Customer {self.receiver_name} "
                             f"in Carrier Tracking {self.name}")
        for emp in frappe.get_all("Employee", filters={"name": ["in", list(employees.values())], "status": ["!=", "Left"]},
                                  fields=["user_id"]):
            email = get_email_id(emp.user_id)
            if email and len(email) < 140:
                self.sales_person_email = email


@frappe.whitelist()
def carrier_name_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
    """Transporters with an API mode (#168)."""
    return frappe.get_all("Transporters", filters={"api_mode": ["!=", "None"], "name": ["like", f"%{txt}%"]},
                          fields=["name"], order_by="name asc", start=start, page_length=page_len,
                          as_list=not as_dict)
