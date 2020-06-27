# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import re
import frappe
from fedex.tools.conversion import sobject_to_dict
from frappe.website.website_generator import WebsiteGenerator
from frappe.utils import flt
from frappe.utils.file_manager import remove_all
from ...scheduled_tasks.shipment_data_update import getOrderShipmentDetails, pushOrderData, courier_charges_validation
from ...validations.sales_invoice import create_new_carrier_track
from .fedex_functions import shipment_booking, start_delete_shipment, get_signature_proof, \
    validate_address, get_rates_from_fedex, get_available_services
from ....utils.sales_utils import validate_address_google_update


class CarrierTracking(WebsiteGenerator):
    allowed_docs_items = ['Sales Invoice', 'Purchase Order']

    def pushdata(self):
        pushOrderData(self)

    def get_status(self):
        if self.status == "":
            if frappe.get_value("Transporters", self.carrier_name, "fedex_credentials") == 1:
                frappe.throw("First Book the Shipment.")
        if self.status is not None or self.status != "Not Booked" or self.status != "":
            getOrderShipmentDetails(self)
        else:
            frappe.throw("First Book the Shipment.")

    def get_sign_proof(self):
        get_signature_proof(self)

    def address_validation(self):
        validate_address(self)

    def autoname(self):
        if self.get("__is_local") == 1:
            self.validate()

    def validate(self):
        if self.to_address:
            validate_address_google_update(self.to_address)
        if self.from_address:
            validate_address_google_update(self.from_address)
        if self.docstatus != 1:
            self.published = 0
            self.route = ""
        if self.status == "" or self.status == "Not Booked":
            pass
        else:
            self.docstatus = 1
        if self.published == 1:
            self.route = self.name.lower()
        else:
            self.route = ""
        trans_doc = frappe.get_doc("Transporters", self.carrier_name)
        if trans_doc.track_on_shipway != 1 and trans_doc.fedex_credentials != 1 and trans_doc.fedex_tracking_only != 1:
            if trans_doc.docstatus != 1:
                trans_doc.docstatus = 1
                trans_doc.manual_exception_removed = 1
        self.update_fields(trans_doc)
        from_address_doc = frappe.get_doc("Address", self.from_address)
        to_address_doc = frappe.get_doc("Address", self.to_address)
        contact_doc = frappe.get_doc("Contact", self.contact_person)
        self.gen_add_validations(trans_doc, from_address_doc, to_address_doc)
        self.set_recipient_email(to_address_doc, contact_doc)
        if trans_doc.fedex_credentials == 1:
            self.fedex_account_number = trans_doc.fedex_account_number
            self.sales_invoice_validations_fedex()
            self.ctrack_validations()
            courier_charges_validation(self, trans_doc)
            self.carrier_validations(trans_doc, from_address_doc, to_address_doc)
        else:
            self.non_fedex_validations()
        #self.auto_submit_ctrack(trans_doc)

    def auto_submit_ctrack(self, trans_doc):
        if trans_doc.fedex_credentials == 1:
            if self.status is not None and self.status != "Booked":
                self.flags.ignore_permissions = True
                self.submit()
        elif trans_doc.track_on_shipway == 1:
            if self.status is not None and self.status not in ["Posting Error", "Shipment Data Uploaded",
                                                               "Pickup Scheduled", "Pickup Scheduled", "Booked"]:
                self.submit()

    def on_submit(self):
        self.published = 1
        self.route = self.name.lower()
        self.push_data_to_sales_invoice()

    def on_cancel(self):
        frappe.db.set_value("Carrier Tracking", self.name, "published", 0)
        frappe.db.set_value("Carrier Tracking", self.name, "route", "")

    def push_data_to_sales_invoice(self):
        if self.document == 'Sales Invoice':
            frappe.db.set_value('Sales Invoice', self.document_name, 'transporters', self.carrier_name)
            frappe.db.set_value('Sales Invoice', self.document_name, 'lr_no', self.awb_number)

    def update_fields(self, trans_doc):
        if self.document == 'Sales Invoice':
            si_doc = frappe.get_doc("Sales Invoice", self.document_name)
            self.receiver_document = "Customer"
            self.receiver_name = si_doc.customer
            tax_temp_doc = frappe.get_doc("Sales Taxes and Charges Template", \
                                          si_doc.taxes_and_charges)
            if not self.from_address and self.get("__islocal") == 1:
                if not tax_temp_doc.from_address:
                    frappe.throw("Update From Address in Tax Template {}".format(tax_temp_doc.name))
                else:
                    self.from_address = tax_temp_doc.from_address
            elif not self.from_address:
                frappe.throw("From Address is Needed before Saving the Document")
            self.to_address = si_doc.shipping_address_name
            self.contact_person = si_doc.contact_person
            #self.carrier_name = si_doc.transporters
            if tax_temp_doc.is_sample == 1:
                self.purpose = 'SAMPLE'
                if self.amount == 0:
                    self.amount = 1
            else:
                self.purpose = 'SOLD'
                self.amount = si_doc.grand_total
            self.currency = si_doc.currency
            chrgd_courier = 0
            for d in si_doc.items:
                if d.income_account == trans_doc.invoice_courier_charges_account:
                    chrgd_courier += d.base_amount
            self.courier_charged = chrgd_courier
        elif self.document == 'Purchase Order':
            po_doc = frappe.get_doc("Purchase Order", self.document_name)
            self.receiver_document = "Supplier"
            self.receiver_name = po_doc.supplier
            tax_temp_doc = frappe.get_doc("Purchase Taxes and Charges Template", \
                                          po_doc.taxes_and_charges)
            if not self.from_address and self.get("__islocal") == 1:
                if not tax_temp_doc.from_address:
                    frappe.throw("Update From Address in Tax Template {}".format(tax_temp_doc.name))
                else:
                    self.from_address = tax_temp_doc.from_address
            elif not self.from_address:
                frappe.throw("From Address is Needed before Saving the Document")
            self.to_address = po_doc.supplier_address
            self.contact_person = po_doc.contact_person
            self.purpose = 'NOT_SOLD'
            self.amount = po_doc.grand_total
            self.currency = po_doc.currency
        elif self.document in ('Customer', 'Supplier', 'Company', 'Sales Partner', 'Employee'):
            if not self.carrier_name:
                frappe.throw('Select the Carrier Through which Shipment is to be Sent')
            if not self.purpose:
                frappe.throw('Select the Purpose of Shipment')
            if not self.from_address:
                frappe.throw('Select the Address from which Shipment is to be Sent')
            if not self.shipment_notes:
                frappe.throw('Add a Small description of the Type of Things in Consignment in Shipment Notes')
            cu_doc = frappe.get_doc(self.document, self.document_name)
            self.receiver_document = self.document
            self.receiver_name = self.document_name
            # Validate To Address and contact person of customer or supplier only
            if not self.to_address:
                def_to_add = frappe.db.sql("""SELECT ad.name FROM `tabAddress` ad, `tabDynamic Link` dl 
                WHERE  dl.link_doctype = '%s' AND dl.link_name = '%s' AND dl.parent = ad.name""" %
                                           (self.document, self.document_name), as_list=1)
                self.to_address = def_to_add[0][0]
            if not self.contact_person:
                def_contact = frappe.db.sql("""SELECT con.name FROM `tabContact` con, `tabDynamic Link` dl 
                WHERE  dl.link_doctype = '%s' AND dl.link_name = '%s' AND dl.parent = con.name""" %
                                            (self.document, self.document_name), as_list=1)
                self.contact_person = def_contact[0][0]
            if self.to_address or self.contact_person:
                linked_add = frappe.db.sql("""SELECT link_name FROM `tabDynamic Link` WHERE parent = '%s' AND 
                link_doctype = '%s' AND link_name = '%s'""" % (self.to_address, self.document, self.document_name))
                if not linked_add:
                    frappe.throw("To Address: {} not from {}: {}". \
                                 format(self.to_address, self.document, self.document_name))
                linked_con = frappe.db.sql("""SELECT link_name FROM `tabDynamic Link` WHERE parent = '%s' AND 
                link_doctype = '%s' AND link_name = '%s'""" % (self.to_address, self.document, self.document_name))
                if not linked_con:
                    frappe.throw("Contact: {} not from {}: {}". \
                                 format(self.contact_person, self.document, self.document_name))
            if not self.amount:
                self.amount = 1
            self.currency = 'INR'

    def non_fedex_validations(self):
        if self.document == 'Sales Invoice':
            si_doc = frappe.get_doc("Sales Invoice", self.document_name)
            if self.invoice_integrity != 1:
                if self.posted_to_shipway == 1:
                    si_awb = re.sub('[^A-Za-z0-9]+', '', str(si_doc.lr_no))
                    if re.sub('[^A-Za-z0-9]+', '', str(self.awb_number)) != si_awb or \
                            si_doc.transporters != self.carrier_name:
                        create_new_carrier_track(si_doc, frappe)
                        self.submit()
                        # self.save(ignore_permissions=True)
                #else:
                    #self.awb_number = si_doc.lr_no
                    #self.carrier_name = si_doc.transporters

    def gen_add_validations(self, trans_doc, from_address_doc, to_address_doc):
        if self.status == "Delivered":
            frappe.db.set_value("Carrier Tracking", self.name, "docstatus", 1)
        if from_address_doc.pincode is None:
            frappe.throw(("No Pincode Defined for Address {} if pincode not known enter NA").format(self.from_address))
        if self.document == 'Sales Invoice':
            si_doc = frappe.get_doc("Sales Invoice", self.document_name)
            if self.carrier_name == si_doc.transporters and self.awb_number == si_doc.lr_no:
                self.invoice_integrity = 1
            else:
                self.invoice_integrity = 0

    def carrier_validations(self, trans_doc, from_address_doc, to_address_doc):
        contact_doc = frappe.get_doc('Contact', self.contact_person)
        if trans_doc.is_outward_only == 1:
            if self.is_inward != 1:
                if from_address_doc.is_your_company_address != 1:
                    frappe.throw(('Since {} is Outward Transporter, From Address Should be Owned Address').
                                 format(self.carrier_name))
            else:
                if from_address_doc.is_your_company_address == 1:
                    frappe.throw(('Since {} is Marked For Inward Shipment, From Address Should Not be Owned Address').
                                 format(self.carrier_name))
        else:
            if from_address_doc.is_your_company_address == 1:
                frappe.throw(('Since {} is Inward Transporter, From Address Should be not be Owned Address').
                             format(self.carrier_name))
            if to_address_doc.is_your_company_address != 1:
                frappe.throw(('Since {} is Inward Transporter, To Address Should be Owned Address').
                             format(self.carrier_name))
        if trans_doc.is_export_only == 1:
            if from_address_doc.country == to_address_doc.country:
                frappe.throw(('Since {} is Export Transporter, To Address Should be not be in {}').
                             format(self.carrier_name, from_address_doc.country))
        if trans_doc.is_imports_only == 1:
            if from_address_doc.is_your_company_address == 1:
                frappe.throw(('Since {} is Import Transporter, From Address Should be not owned Address').
                             format(self.carrier_name))
            if from_address_doc.country == to_address_doc.country:
                frappe.throw(('Since {} is Import Transporter, From Address Country Should not be Same as To Address').
                             format(self.carrier_name))
            if from_address_doc.is_your_company_address != 1:
                frappe.throw(('Since {} is Import Transporter,To Address Should be Owned Address').
                             format(self.carrier_name))
        if trans_doc.is_domestic_only == 1:
            if from_address_doc.country != to_address_doc.country:
                frappe.throw(('Since {} is Domestic Transporter, From and To Address Should be in Same Country').
                             format(self.carrier_name))
        if flt(trans_doc.minimum_weight) > 0 and self.get("__islocal") != 1:
            if flt(trans_doc.minimum_weight) > flt(self.total_weight):
                frappe.throw(('Minimum Weight for {} is {} kgs').format(self.carrier_name, trans_doc.minimum_weight))
        if trans_doc.maximum_amount > 0:
            if trans_doc.maximum_amount < self.amount:
                frappe.throw(('Maximum Value for {} is {}').format(self.carrier_name, trans_doc.maximum_amount))
        if self.amount < 1:
            frappe.throw("Amount Should be One or More than One")

    def ctrack_validations(self):
        # Only allow SYSTEM MANAGER to make changes to the DOCUMENT with SENDER
        # DUTIES PAYMENT (Very RISKY OPTION hence this Validation)
        if self.duties_payment_by == 'SENDER':
            user = frappe.session.user
            roles = frappe.db.sql("""SELECT role FROM `tabHas Role` WHERE parent = '%s' """ % user, as_list=1)
            if any("System Manager" in s for s in roles):
                pass
            else:
                frappe.throw("Only System Managers are Allowed to Make Changes to {} as Duties Payment is by {}".
                             format(self.name, self.duties_payment_by))
        # Update Package Details and also Validate UOM and Volumetric Weight
        for pkg in self.shipment_package_details:
            pkg_doc = frappe.get_doc("Shipment Package", pkg.shipment_package)
            pkg.package_name = pkg_doc.title
            pkg.volumetric_weight = pkg_doc.volumetric_weight_in_kgs
            if pkg.weight_uom != 'Kg':
                frappe.throw("Only Kg is allowed currently in Package Weight UoM")
            if flt(pkg.volumetric_weight) > flt(pkg.package_weight):
                frappe.throw("Parcel Weight Less than Volumetric Weight, USE Smaller Package or Change the "
                             "Weight in Row {}".format(pkg.idx))

    def sales_invoice_validations_fedex(self):
        if self.document in CarrierTracking.allowed_docs_items:
            si_doc = frappe.get_doc(self.document, self.document_name)
            other_tracks = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking`WHERE document = '%s' AND 
            document_name = '%s' AND docstatus != 2 AND name != '%s'""" %
                                         (self.document, self.document_name, self.name), as_list=1)
            if other_tracks:
                frappe.throw('{}: {} is already linked to {}'.format(self.document, self.document_name,
                                                                     other_tracks[0][0]))
            if self.awb_number:
                if self.awb_number != si_doc.lr_no:
                    self.push_data_to_sales_invoice()
                    #self.set_invoice_lr_no(self.document_name, self.document)
        else:
            if self.purpose == 'SOLD':
                frappe.throw('Purpose SOLD only possible for Sales Invoices')
        total_weight = 0
        if self.shipment_package_details:
            for d in self.shipment_package_details:
                total_weight += d.package_weight
                self.weight_uom = d.weight_uom
                self.total_handling_units = d.idx
            if total_weight > 0:
                if flt(self.total_weight) != flt(total_weight):
                    self.total_weight = total_weight
        #else:
            #frappe.throw("Shipment Package Details Manadatory for Fedex Booking for {}".format(self.name))

    def validate_empty_shipment(self):
        if self.shipment_package_details:
            pass
        else:
            frappe.throw("Shipment Package Details Manadatory for Fedex Booking for {}".format(self.name))


    def available_services(self):
        get_available_services(self)

    def get_rates(self):
        self.validate()
        self.validate_empty_shipment()
        get_rates_from_fedex(self)

    def book_shipment(self):
        self.validate()
        self.validate_empty_shipment()
        if self.shipment_package_details:
            for packages in self.shipment_package_details:
                if packages.tracking_id and packages.idx == 1:
                    frappe.throw(("Shipment Already Booked with Tracking Number: {}").format(self.awb_number))
                else:
                    if self.get("__islocal") != 1:
                        if packages.idx == 1:
                            shipment_booking(self)
                            self.published = 1
                            self.route = self.name.lower()
                            self.docstatus = 1
                            self.save(ignore_permissions=True)
                    else:
                        frappe.throw('Save the Transaction before Booking Shipment')
        else:
            frappe.throw("To Book Shipment, Package Details is Mandatory")

    def delete_shipment(self):
        if self.status == "Booked":
            try:
                start_delete_shipment(self)
            except:
                frappe.msgprint(('Some ERROR guess AWB not found on Fedex for AWB# {}').format(self.awb_number))

            frappe.db.set_value("Carrier Tracking", self.name, "docstatus", 0)
            frappe.db.set_value("Carrier Tracking", self.name, "awb_number", "NA")
            frappe.db.set_value("Carrier Tracking", self.name, "status_code", "")
            frappe.db.set_value("Carrier Tracking", self.name, "published", 0)
            frappe.db.set_value("Carrier Tracking", self.name, "route", "")
            frappe.db.set_value("Carrier Tracking", self.name, "status", "Not Booked")
            if self.document == 'Sales Invoice':
                self.push_data_to_sales_invoice()

            shp_pkg_dt = frappe.db.sql("""SELECT name FROM `tabShipment Package Details` 
                WHERE parent = '%s'""" % (self.name), as_list=1)
            for shp in shp_pkg_dt:
                frappe.db.set_value("Shipment Package Details", shp[0], "docstatus", 0)
                frappe.db.set_value("Shipment Package Details", shp[0], "tracking_id", "")
            remove_all(self.doctype, self.name)
        else:
            frappe.throw(("Only Booked Shipments Can be Deleted, {} is in {} Stage").format(self.name, self.status))

    def set_recipient_email(self, to_address_doc, contact_doc):
        if self.receiver_document == "Customer":
            cust_doc = frappe.get_doc(self.receiver_document, self.receiver_name)
            for sp in cust_doc.sales_team:
                employee = frappe.get_value("Sales Person", sp.sales_person, "employee")
                if employee:
                    emp_doc = frappe.get_doc("Employee", employee)
                else:
                    frappe.throw("No Employee Linked with Sales Person {} for Customer {} in Carrier "
                                 "Tracking {}".format(sp.sales_person, self.receiver_name, self.name))
                if emp_doc.status != 'Left':
                    sper_email = emp_doc.user_id
                    if len(sper_email) < 140:
                        self.sales_person_email = sper_email
        if to_address_doc.email_id != contact_doc.email_id:
            if len(str(to_address_doc.email_id) + ", " + str(contact_doc.email_id)) < 140:
                self.customer_emails = str(to_address_doc.email_id) + ", " + str(contact_doc.email_id)
            else:
                if len(str(contact_doc.email_id)) < 140:
                    self.customer_emails = contact_doc.email_id
                elif len(to_address_doc.email_id) < 140:
                    self.customer_emails = to_address_doc.email_id
        else:
            if len(str(contact_doc.email_id)) < 140:
                self.customer_emails = contact_doc.email_id
            elif len(to_address_doc.email_id) < 140:
                self.customer_emails = to_address_doc.email_id

    def location_service(self, credentials, from_address_doc, from_country_doc):
        from fedex.services.location_service import FedexSearchLocationRequest
        customer_transaction_id = "*** LocationService Request v3 using Python ***"
        # Optional transaction_id
        location_request = FedexSearchLocationRequest(credentials, customer_transaction_id=customer_transaction_id)
        location_request.Constraints.RadiusDistance.Value = self.radius
        location_request.Constraints.RadiusDistance.Units = self.radius_uom
        location_request.Address.PostalCode = from_address_doc.pincode[0:10]
        location_request.Address.CountryCode = from_country_doc.code
        location_request.send_request()
        response_dict = sobject_to_dict(location_request.response)
        frappe.msgprint(str(response_dict))

    def set_invoice_lr_no(self, si_name, si_doc):
        if self.awb_number:
            frappe.db.set_value(si_doc, si_name, "lr_no", self.awb_number)
        else:
            frappe.db.set_value(si_doc, si_name, "lr_no", "NA")


'''
    @staticmethod
    def get_company_data(request_data, field_name):
        shipper_details = frappe.db.get_value("Address", request_data.get("shipper_id"), "*", as_dict=True)
        field_value = frappe.db.get_value("Company", shipper_details.get("company"), field_name)
        return shipper_details, field_value
'''
