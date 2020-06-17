# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import re
import frappe
import base64
from datetime import datetime
from datetime import date
from frappe.utils import flt, cstr
from fedex.tools.conversion import sobject_to_dict
from frappe.utils.file_manager import save_file

uom_mapper = {"Kg": "KG", "LB": "LB", "kg": "KG", "cm": "CM"}
allowed_docs = ['Sales Invoice', 'Purchase Order', 'Customer', 'Supplier', 'Company', 'Employee', 'Sales Partner']
allowed_docs_items = ['Sales Invoice', 'Purchase Order']

def get_rates_from_fedex(track_doc):
    credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, transporter_doc, \
    contact_doc = get_required_docs(track_doc)
    rate_service(track_doc, credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc,
                 transporter_doc)

def shipment_booking(track_doc):
    credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
    transporter_doc, contact_doc = get_required_docs(track_doc)

    rate_service(track_doc, credentials, from_address_doc, to_address_doc, from_country_doc,
                 to_country_doc, transporter_doc)
    create_shipment_service(track_doc, credentials, from_address_doc, to_address_doc,
                            from_country_doc, to_country_doc, transporter_doc, contact_doc)

def start_delete_shipment(track_doc):
    credentials = get_required_docs(track_doc)[0]
    transporter_doc = get_required_docs(track_doc)[5]
    delete_shipment_service(track_doc, credentials, transporter_doc)


def validate_address(track_doc):
    credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
    transporter_doc, contact_doc = get_required_docs(track_doc)
    address_validation(credentials, to_address_doc, to_country_doc)


def get_available_services(track_doc):
    credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, transporter_doc, \
    contact_doc = get_required_docs(track_doc)

    availabiltiy_commitment(credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc)


def create_shipment_service(track_doc, credentials, from_address_doc, to_address_doc, from_country_doc,
                            to_country_doc, transporter_doc, contact_doc):
    from fedex.services.ship_service import FedexProcessShipmentRequest
    customer_transaction_id = track_doc.name  # Optional transaction_id
    shipment = FedexProcessShipmentRequest(credentials, customer_transaction_id=customer_transaction_id)
    set_shipment_details(track_doc, shipment, credentials, transporter_doc)
    set_shipper_info(shipment, from_address_doc, credentials)
    set_recipient_info(track_doc, shipment, to_address_doc, credentials)
    set_fedex_label_info(shipment)
    set_commodities_info(track_doc, shipment)
    set_commercial_invoice_info(track_doc, shipment)

    pkg_count = track_doc.total_handling_units
    for index, pkg in enumerate(track_doc.shipment_package_details):
        pkg_doc = frappe.get_doc("Shipment Package", pkg.shipment_package)
        if index:
            shipment.RequestedShipment.MasterTrackingId.TrackingNumber = track_doc.awb_number
            shipment.RequestedShipment.MasterTrackingId.TrackingIdType.value = \
                transporter_doc.type_of_service
            set_package_data(track_doc, pkg, pkg_doc, shipment, index + 1)
        else:
            shipment.RequestedShipment.TotalWeight.Units = uom_mapper.get(track_doc.weight_uom)
            shipment.RequestedShipment.TotalWeight.Value = track_doc.total_weight
            set_package_data(track_doc, pkg, pkg_doc, shipment, index + 1)
            shipment.send_validation_request()
        shipment.send_request()

        validate_fedex_shipping_response(shipment, pkg.idx)
        tracking_id = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].TrackingIds[
            0].TrackingNumber
        if index == 0:
            track_doc.awb_number = tracking_id
        track_doc.status = "Booked"
        set_package_details(pkg, cstr(shipment.response), tracking_id)
        store_label(shipment, tracking_id, track_doc.doctype, track_doc.name)
        track_doc.save()
    return shipment


def rate_service(track_doc, credentials, from_address_doc, to_address_doc,
                 from_country_doc, to_country_doc, transporter_doc):
    stop = 0
    from fedex.services.rate_service import FedexRateServiceRequest
    # Optional transaction_id
    customer_transaction_id = "*** RateService Request v18 using Python ***"
    rate_request = FedexRateServiceRequest(credentials, customer_transaction_id=customer_transaction_id)
    rate_request.ReturnTransitAndCommit = True
    rate_request.RequestedShipment.DropoffType = 'REGULAR_PICKUP'
    rate_request.RequestedShipment.ServiceType = transporter_doc.fedex_service_code
    rate_request.RequestedShipment.PackagingType = 'YOUR_PACKAGING'
    rate_request.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER'
    rate_request.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = \
        credentials.account_number
    rate_request.RequestedShipment.CustomsClearanceDetail.DutiesPayment.PaymentType = track_doc.duties_payment_by
    rate_request.RequestedShipment.CustomsClearanceDetail.CustomsValue.Amount = track_doc.amount
    rate_request.RequestedShipment.CustomsClearanceDetail.CustomsValue.Currency = track_doc.currency
    rate_request.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor.ResponsibleParty.AccountNumber = \
        credentials.account_number if track_doc.duties_payment_by == "SENDER" else ""

    set_shipper_info(rate_request, from_address_doc, credentials)
    set_recipient_info(track_doc, rate_request, to_address_doc, credentials)
    # set_commodities_info(track_doc, rate_request)
    set_commercial_invoice_info(track_doc, rate_request)

    for row in track_doc.shipment_package_details:
        package1 = set_package_weight(track_doc, rate_request, row)
        package1.GroupPackageCount = 1
        rate_request.add_package(package1)
    rate_request.send_request()
    # RateReplyDetails can contain rates for multiple ServiceTypes if ServiceType was set to None
    for service in rate_request.response.RateReplyDetails:
        for delivery in service:
            if delivery[0] == 'DeliveryTimestamp':
                track_doc.expected_delivery_date = delivery[1]
        for detail in service.RatedShipmentDetails:
            for surcharge in detail.ShipmentRateDetail.Surcharges:
                if surcharge.SurchargeType == 'OUT_OF_DELIVERY_AREA':
                    stop = 1
                    frappe.msgprint("{}: ODA rate_request charge {}".
                                    format(service.ServiceType, surcharge.Amount.Amount))

        for rate_detail in service.RatedShipmentDetails:
            track_doc.shipment_cost = rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Amount
            track_doc.shipment_cost_currency = rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Currency
            track_doc.save()
    if stop == 1 and track_doc.allow_oda_shipment != 1:
        frappe.throw('Out of Delivery Area, Booking of Shipment Not Allowed')


def get_tracking_from_fedex(track_doc):
    credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, transporter_doc, \
    contact_doc = get_required_docs(track_doc)
    if frappe.get_value("Transporters", track_doc.carrier_name, "fedex_credentials") == 1 or \
        frappe.get_value("Transporters", track_doc.carrier_name, "fedex_tracking_only") == 1:
        fedex_account = 1
    else:
        fedex_account = 0
    if fedex_account == 1:
        from fedex.services.track_service import FedexTrackRequest
        tk_req = FedexTrackRequest(credentials)
        tk_req.SelectionDetails.PackageIdentifier.Value = track_doc.awb_number
        tk_req.ProcessingOptions = 'INCLUDE_DETAILED_SCANS'
        tk_req.IncludeDetailedScans = True
        tk_req.send_request()
        if tk_req.response.HighestSeverity == "SUCCESS":
            response = sobject_to_dict(tk_req.response)
            comp_trks = response.get("CompletedTrackDetails")
            if not comp_trks:
                frappe.msgprint("No Tracking Found for {}".format(track_doc.name))
                if track_doc.docstatus == 1:
                    track_doc.docstatus = 2
                else:
                    track_doc.docstatus = 1
                track_doc.manual_exception_removed = 1
                track_doc.save()
                exit()
            trk_details = comp_trks[0].get('TrackDetails')
            trk_details_status = trk_details[0].get('Notification')
            if trk_details_status.get('Severity') == 'SUCCESS':
                stat_details = trk_details[0].get('StatusDetail')
                status_code = stat_details.get('Code')
                if status_code == 'DL':
                    # if trk_details[0].get('AvailableImages')[0].get('Type') == 'SIGNATURE_PROOF_OF_DELIVERY':
                    #    track_doc.sign_proof = 'SIGNATURE_PROOF_OF_DELIVERY'
                    track_doc.status = 'Delivered'
                    track_doc.recipient = trk_details[0].get('DeliverySignatureName')
                elif status_code == 'CA':
                    track_doc.status = 'Cancelled'
                    track_doc.docstatus = 2
                elif status_code == 'OC':
                    track_doc.status = 'Booked'
                else:
                    track_doc.status = 'In Transit'
                des_dict = trk_details[0].get('DestinationAddress')
                scan_events = trk_details[0].get('Events')
                des_city = des_dict.get('City', None)
                des_state = des_dict.get('StateOrProvinceCode', None)
                des_country = des_dict.get('CountryName', None)
                ship_to_city = (str(des_city) + ", " if des_city is not None else "") + \
                               (str(des_state) + ", " if des_state is not None else "") + \
                               (str(des_country) if des_country is not None else "")
                if trk_details[0].get('DatesOrTimes'):
                    pickup_date = trk_details[0].get('DatesOrTimes')[0].get('DateOrTimestamp')
                    track_doc.pickup_date = datetime.strptime(pickup_date[:19], '%Y-%m-%dT%H:%M:%S')
                scans = []
                if scan_events:
                    for event in scan_events:
                        if event.get('EventType') == 'DL':
                            track_doc.delivery_date_time = event.get('Timestamp').replace(tzinfo=None)
                        row_dict = {"time": event.get('Timestamp').replace(tzinfo=None)}
                        city = event.get('Address').get('City', None)
                        state = event.get('Address').get('StateOrProvinceCode', None)
                        postcode = event.get('Address').get('PostalCode', None)
                        country = event.get('Address').get('CountryName', None)
                        location = (str(city) if city is not None else "") + (", " if city is not None else "") + \
                                   (str(state) if state is not None else "") + (", " if state is not None else "") + \
                                   (str(postcode) if postcode is not None else "") + (
                                       ", " if postcode is not None else "") + \
                                   (str(country) if country is not None else "Base Location")
                        row_dict["location"] = location
                        event_desc = event.get('EventDescription', None)
                        excep_code = event.get('StatusExceptionCode', None)
                        excep_desc = event.get('StatusExceptionDescription', None)
                        event_full_desc = event_desc + (" Excep Code: " if excep_code is not None else "") + \
                                          (str(excep_code) if excep_code is not None else "") + \
                                          " " + (str(excep_desc) if excep_desc is not None else "")
                        row_dict["status_detail"] = event_full_desc
                        scans.append(row_dict)
                else:
                    frappe.throw('NO SCANS Recevied')
                track_doc.scans = []
                track_doc.status_code = status_code
                track_doc.ship_to_city = ship_to_city
                for scan in scans:
                    track_doc.append("scans", scan)
                track_doc.save(ignore_permissions=True)
            else:
                track_doc.manual_exception_removed = 1
                track_doc.docstatus = 2
                #Cancel the doc since the AWB no is WRONG.
                track_doc.add_comment(trk_details_status.get('Message'))
                track_doc.save()
        else:
            print('Failed to Fetch Status from Fedex for {}'.format(track_doc.name))
            frappe.msgprint('Failed to Fetch Status from Fedex for {}'.format(track_doc.name))

    else:
        frappe.throw("Not Fedex Account")


def delete_shipment_service(track_doc, credentials, transporter_doc):
    from fedex.services.ship_service import FedexDeleteShipmentRequest
    tracking_id = track_doc.awb_number
    del_request = FedexDeleteShipmentRequest(credentials)
    del_request.DeletionControlType = "DELETE_ALL_PACKAGES"
    del_request.TrackingId.TrackingNumber = tracking_id
    del_request.TrackingId.TrackingIdType = transporter_doc.type_of_service
    try:
        del_request.send_request()
    except Exception as ex:
        frappe.throw('Fedex API: ' + cstr(ex))

    if del_request.response.HighestSeverity == "SUCCESS":
        frappe.msgprint('Shipment with tracking number %s is deleted successfully.' % tracking_id)
    else:
        show_notification(del_request)
        frappe.msgprint('Canceling of Shipment in Fedex service failed.')


def get_signature_proof(track_doc):
    frappe.throw("WIP")
    credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, transporter_doc, \
    contact_doc = get_required_docs(track_doc)
    trans_doc = frappe.get_doc("Transporters", track_doc.carrier_name)
    if track_doc.docstatus == 1 and track_doc.status == 'Delivered' and track_doc.sign_proof == 'SIGNATURE_PROOF_OF_DELIVERY' \
            and trans_doc.fedex_credentials == 1:
        from fedex.services.track_service import FedexTrackRequest
        spod = FedexTrackRequest(credentials)
        # frappe.msgprint(str(spod.__dict__))
        for service in spod:
            frappe.msgprint(str(spod.__dict__))
        spod_req = spod.create_wsdl_object_of_type('GetTrackingDocumentsRequest')
        spod.SelectionDetails.PackageIdentifier.Value = track_doc.awb_number
        # spod_req.SelectionDetails.responseFormat = 'PDF'
        spod_req_doc_specs = spod_req.TrackingDocumentSpecification
        spod_req_doc_specs.DocumentTypes = 'SIGNATURE_PROOF_OF_DELIVERY'
        spod_req_doc_specs.SignatureProofOfDeliveryDetail.DispositionType = 'RETURN'
        spod_req_doc_specs.SignatureProofOfDeliveryDetail.ImageType = 'PDF'
        # frappe.msgprint(str(spod_req.__dict__))
        # frappe.msgprint(str(spod_req_doc_specs.__dict__))
        # frappe.throw(str(spod.__dict__))
        spod.send_request()
        # frappe.msgprint(str(spod.response))
        # label_data = base64.b64decode(spod.response.CompletedShipmentDetail.CompletedPackageDetails[0].Label.Parts[0].Image)
        # track_doc.store_file('FEDEX-ID-{0}.pdf'.format(tracking_id), label_data, ps_doctype, ps_name)
        # track_doc.save()
        frappe.msgprint("Go for Proof")


def address_validation(credentials, add_doc, country_doc):
    from fedex.services.address_validation_service import FedexAddressValidationRequest
    avs_request = FedexAddressValidationRequest(credentials)
    if add_doc.state_rigpl is not None and add_doc.state_rigpl != "":
        state_doc = frappe.get_doc("State", add_doc.state_rigpl)
    else:
        state_doc = ""
    if state_doc != "":
        state_code = state_doc.state_code
    else:
        state_code = ""
    address1 = avs_request.create_wsdl_object_of_type('AddressToValidate')
    address1.Address.StreetLines = [str(add_doc.address_line1)[0:35], \
                                    str(add_doc.address_line2)[0:35]]
    address1.Address.City = str(add_doc.city)[0:20]
    address1.Address.StateOrProvinceCode = str(state_code)[0:2]
    address1.Address.PostalCode = str(add_doc.pincode)[0:10]
    address1.Address.CountryCode = str(country_doc.code)[0:2]
    address1.Address.CountryName = add_doc.country
    address1.Address.Residential = add_doc.is_residential
    avs_request.add_address(address1)
    avs_request.send_request()

    for i in range(len(avs_request.response.AddressResults)):
        frappe.msgprint("Details for Address {}".format(i + 1))
        frappe.msgprint("The validated street is: {}"
                        "".format(avs_request.response.AddressResults[i].EffectiveAddress.StreetLines))
        frappe.msgprint("The validated city is: {}"
                        "".format(avs_request.response.AddressResults[i].EffectiveAddress.City))
        frappe.msgprint("The validated state code is: {}"
                        "".format(avs_request.response.AddressResults[i].EffectiveAddress.StateOrProvinceCode))
        frappe.msgprint("The validated postal code is: {}"
                        "".format(avs_request.response.AddressResults[i].EffectiveAddress.PostalCode))
        frappe.msgprint("The validated country code is: {}"
                        "".format(avs_request.response.AddressResults[i].EffectiveAddress.CountryCode))


def availabiltiy_commitment(credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc):
    from fedex.services.availability_commitment_service import FedexAvailabilityCommitmentRequest
    avc_request = FedexAvailabilityCommitmentRequest(credentials)
    avc_request.Origin.PostalCode = str(from_address_doc.pincode)[0:10]
    avc_request.Origin.CountryCode = from_country_doc.code
    avc_request.Destination.PostalCode = str(to_address_doc.pincode)[0:10]
    avc_request.Destination.CountryCode = to_country_doc.code
    avc_request.ShipDate = date.today()
    avc_request.send_request()
    for option in avc_request.response.Options:
        frappe.msgprint("Ship Option:")
        if hasattr(option, 'Service'):
            frappe.msgprint("Service {}".format(option.Service))
        if hasattr(option, 'DeliveryDate'):
            frappe.msgprint("DeliveryDate {}".format(option.DeliveryDate))
        if hasattr(option, 'DeliveryDay'):
            frappe.msgprint("DeliveryDay {}".format(option.DeliveryDay))
        if hasattr(option, 'TransitTime'):
            frappe.msgprint("TransitTime {}".format(option.TransitTime))
        frappe.msgprint("")


def get_required_docs(track_doc):
    transporter_doc = frappe.get_doc("Transporters", track_doc.carrier_name)
    if transporter_doc.fedex_credentials == 1:
        fedex_cred = 1
    elif transporter_doc.fedex_tracking_only == 1:
        fedex_cred = 1
    else:
        fedex_cred = 0
    if fedex_cred != 1:
        frappe.throw("{0} is not a Valid Fedex Account".format(track_doc.carrier_name))
    to_address_doc = frappe.get_doc("Address", track_doc.to_address)
    to_country_doc = frappe.get_doc("Country", to_address_doc.country)
    contact_doc = frappe.get_doc("Contact", track_doc.contact_person)
    from_address_doc = frappe.get_doc("Address", track_doc.from_address)
    from_country_doc = frappe.get_doc("Country", from_address_doc.country)
    credentials = get_fedex_credentials(transporter_doc)
    return credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, transporter_doc, contact_doc


def set_shipper_info(call_type, ship_add_doc, credentials):
    from_country_doc = frappe.get_doc("Country", ship_add_doc.country)
    tin_no = ship_add_doc.gstin
    if (ship_add_doc.state_rigpl is not None and ship_add_doc.state_rigpl != "") \
            and (ship_add_doc.country == 'India' or ship_add_doc.country == 'United States'):
        state_doc = frappe.get_doc("State", ship_add_doc.state_rigpl)
    else:
        state_doc = ""
    if state_doc != "":
        state_code = state_doc.state_code
    else:
        state_code = ""
    call_type.RequestedShipment.Shipper.AccountNumber = credentials.account_number
    call_type.RequestedShipment.Shipper.Contact.PersonName = str(ship_add_doc.address_title)[0:35]
    call_type.RequestedShipment.Shipper.Contact.CompanyName = str(ship_add_doc.address_title)[0:35]
    call_type.RequestedShipment.Shipper.Contact.PhoneNumber = str(ship_add_doc.phone)[0:15]
    call_type.RequestedShipment.Shipper.Address.StreetLines = [str(ship_add_doc.address_line1)[0:35],
                                                               str(ship_add_doc.address_line2)[0:35]]
    call_type.RequestedShipment.Shipper.Address.City = str(ship_add_doc.city)[0:20]
    call_type.RequestedShipment.Shipper.Address.StateOrProvinceCode = state_code
    call_type.RequestedShipment.Shipper.Address.PostalCode = str(ship_add_doc.pincode)[0:10]
    call_type.RequestedShipment.Shipper.Address.CountryCode = from_country_doc.code
    call_type.RequestedShipment.Shipper.Address.Residential = ship_add_doc.is_residential
    if tin_no != 'NA' and tin_no is not None:
        tin_details = call_type.create_wsdl_object_of_type('TaxpayerIdentification')
        tin_details.TinType.value = "BUSINESS_NATIONAL"
        tin_details.Number = tin_no
        call_type.RequestedShipment.Shipper.Tins = [tin_details]


def set_recipient_info(track_doc, call_type, ship_add_doc, credentials):
    to_country_doc = frappe.get_doc("Country", ship_add_doc.country)
    contact_doc = frappe.get_doc("Contact", track_doc.contact_person)
    if contact_doc.salutation:
        sal = contact_doc.salutation + " "
    else:
        sal = ""
    if contact_doc.first_name:
        first_n = contact_doc.first_name + " "
    else:
        first_n = ""
    if contact_doc.last_name:
        last_n = contact_doc.last_name
    else:
        last_n = ""
    full_name = sal + first_n + last_n

    tin_no = ship_add_doc.gstin
    if ship_add_doc.state_rigpl is not None and ship_add_doc.state_rigpl != "":
        state_doc = frappe.get_doc("State", ship_add_doc.state_rigpl)
    else:
        state_doc = ""
    if state_doc != "":
        state_code = state_doc.state_code
    else:
        state_code = ""

    call_type.RequestedShipment.Recipient.Contact.PersonName = \
        full_name[0:35]
    call_type.RequestedShipment.Recipient.Contact.CompanyName = \
        str(ship_add_doc.address_title)[0:35]
    call_type.RequestedShipment.Recipient.Contact.PhoneNumber = \
        (str(contact_doc.phone) + str(contact_doc.mobile_no))[0:15]
    call_type.RequestedShipment.Recipient.Address.StreetLines = \
        [str(ship_add_doc.address_line1)[0:35], str(ship_add_doc.address_line2)[0:35]]
    call_type.RequestedShipment.Recipient.Address.City = str(ship_add_doc.city)[0:20]
    call_type.RequestedShipment.Recipient.Address.StateOrProvinceCode = state_code
    call_type.RequestedShipment.Recipient.Address.PostalCode = str(ship_add_doc.pincode)[0:10]
    call_type.RequestedShipment.Recipient.Address.CountryCode = to_country_doc.code
    call_type.RequestedShipment.Recipient.Address.Residential = ship_add_doc.is_residential
    call_type.RequestedShipment.EdtRequestType = 'NONE'  # Can be ALL or NONE
    call_type.RequestedShipment.FreightShipmentDetail.TotalHandlingUnits = \
        track_doc.total_handling_units
    if tin_no != 'NA' and tin_no is not None:
        tin_details = call_type.create_wsdl_object_of_type('TaxpayerIdentification')
        tin_details.TinType.value = "BUSINESS_NATIONAL"
        tin_details.Number = tin_no
        call_type.RequestedShipment.Recipient.Tins = [tin_details]

    track_doc.recipient_details = "\n".join([str(ship_add_doc.address_title)[0:35], full_name,
                                             str(ship_add_doc.phone)[0:15], str(ship_add_doc.address_line1)[0:35],
                                             str(ship_add_doc.address_line2)[0:35], str(ship_add_doc.city)[0:20] + " " +
                                             str(state_code) + " " + str(ship_add_doc.pincode)[0:10] + " " +
                                             to_country_doc.code])


def set_shipment_details(track_doc, call_type, credentials, transporter_doc):
    call_type.RequestedShipment.DropoffType = 'REGULAR_PICKUP'  # track_doc.drop_off_type
    call_type.RequestedShipment.ServiceType = transporter_doc.fedex_service_code
    call_type.RequestedShipment.PackagingType = 'YOUR_PACKAGING'  # track_doc.packaging_type
    call_type.RequestedShipment.ShippingChargesPayment.PaymentType = 'THIRD_PARTY'  # track_doc.shipping_payment_by
    call_type.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = \
        credentials.account_number
    call_type.RequestedShipment.CustomsClearanceDetail.DutiesPayment.PaymentType = track_doc.duties_payment_by
    call_type.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor.ResponsibleParty.AccountNumber = \
        credentials.account_number if track_doc.duties_payment_by == "SENDER" else ""
    return call_type


def set_fedex_label_info(shipment):
    shipment.RequestedShipment.LabelSpecification.LabelFormatType = "COMMON2D"
    shipment.RequestedShipment.LabelSpecification.ImageType = 'PDF'
    shipment.RequestedShipment.LabelSpecification.LabelStockType = 'PAPER_8.5X11_TOP_HALF_LABEL'
    shipment.RequestedShipment.LabelSpecification.LabelPrintingOrientation = 'BOTTOM_EDGE_OF_TEXT_FIRST'
    shipment.RequestedShipment.EdtRequestType = 'NONE'

    if hasattr(shipment.RequestedShipment.LabelSpecification, 'LabelOrder'):
        del shipment.RequestedShipment.LabelSpecification.LabelOrder  # Delete, not using.


def set_commodities_info(track_doc, shipment):
    if track_doc.document in allowed_docs_items:
        doc = frappe.get_doc(track_doc.document, track_doc.document_name)
        total_qty = 0
        for row in doc.items:
            total_qty += row.get("qty")
            hsn_doc = frappe.get_doc("GST HSN Code",
                                     frappe.get_value('Item', row.get('item_code'), 'customs_tariff_number'))
            item_doc = frappe.get_doc("Item", row.get("item_code"))
            country_doc = frappe.get_doc("Country", item_doc.country_of_origin)
            country_code = country_doc.code
        commodity_dict = {
            # "Name":row.get("item_code"),
            "Description": hsn_doc.description[0:30],
            "Weight": {"Units": uom_mapper.get(track_doc.weight_uom), "Value": track_doc.total_weight},
            "NumberOfPieces": int(track_doc.total_handling_units),
            "HarmonizedCode": hsn_doc.name[0:8],
            "CountryOfManufacture": country_code,
            "Quantity": int(total_qty),
            "QuantityUnits": "EA",
            "UnitPrice": {"Currency": doc.currency, "Amount": (doc.grand_total / total_qty)
            if track_doc.purpose == 'SOLD' else (1 / total_qty)},
            "CustomsValue": {"Currency": doc.currency, "Amount": doc.grand_total if track_doc.purpose == 'SOLD' else 1}
        }
        shipment.RequestedShipment.CustomsClearanceDetail.Commodities.append(commodity_dict)
    elif track_doc.document in allowed_docs:
        total_qty = track_doc.total_handling_units
        desc = "OTHER PRINTED MATTER, INCLUDING PRINTED PICTURES AND PHOTOGRAPHS TRADE ADVERTISING MATERIAL, " \
               "COMMERCIAL CATALOGUES AND THE LIKE : POSTERS, PRINTED"
        country_doc = frappe.get_doc("Country", frappe.get_value("Address", track_doc.from_address, "country"))
        country_code = country_doc.code
        commodity_dict = {
            # "Name":row.get("item_code"),
            "Description": desc[0:30],
            "Weight": {"Units": uom_mapper.get(track_doc.weight_uom), "Value": track_doc.total_weight},
            "NumberOfPieces": int(track_doc.total_handling_units),
            "HarmonizedCode": '49111010',
            "CountryOfManufacture": country_code,
            "Quantity": int(total_qty),
            "QuantityUnits": "EA",
            "UnitPrice": {"Currency": track_doc.currency, "Amount": (track_doc.amount / total_qty)},
            "CustomsValue": {"Currency": track_doc.currency, "Amount": track_doc.amount}
        }
        shipment.RequestedShipment.CustomsClearanceDetail.Commodities.append(commodity_dict)
        total_value = track_doc.amount
    else:
        frappe.throw("Currently only Booking Shipment is Available vide {}".format(allowed_docs))
        total_value = track_doc.amount


def set_commercial_invoice_info(track_doc, call_type):
    call_type.RequestedShipment.CustomsClearanceDetail.CommercialInvoice.Purpose = track_doc.purpose
    if call_type == 'shipment':
        call_type.RequestedShipment.CustomsClearanceDetail.CommercialInvoice.CustomsInvoiceNumber = \
            track_doc.document_name if track_doc.purpose == 'SOLD' else 'NA'

    call_type.RequestedShipment.ShippingDocumentSpecification.ShippingDocumentTypes = \
        "COMMERCIAL_INVOICE" if track_doc.purpose == 'SOLD' else 'LABEL'

    call_type.RequestedShipment.ShippingDocumentSpecification.CommercialInvoiceDetail.Format.ImageType = "PDF"
    call_type.RequestedShipment.ShippingDocumentSpecification.CommercialInvoiceDetail.Format.StockType = \
        "PAPER_LETTER"
    call_type.RequestedShipment.CustomsClearanceDetail.CustomsValue.Amount = track_doc.amount
    call_type.RequestedShipment.CustomsClearanceDetail.CustomsValue.Currency = track_doc.currency


def set_package_data(track_doc, pkg, pkg_doc, shipment, pkg_no):
    package = set_package_weight(track_doc, shipment, pkg)
    set_package_dimensions(shipment, pkg_doc, package)
    package.SequenceNumber = pkg_no
    shipment.RequestedShipment.RequestedPackageLineItems = [package]
    shipment.RequestedShipment.PackageCount = track_doc.total_handling_units


def set_package_dimensions(shipment, pkg, package):
    # adding package dimensions
    dimn = shipment.create_wsdl_object_of_type('Dimensions')
    dimn.Length = pkg.length
    dimn.Width = pkg.width
    dimn.Height = pkg.height
    dimn.Units = uom_mapper.get(pkg.uom)
    package.Dimensions = dimn


def set_package_weight(track_doc, shipment, pkg):
    package = shipment.create_wsdl_object_of_type('RequestedPackageLineItem')
    package.PhysicalPackaging = 'BOX'
    # adding package weight
    package_weight = shipment.create_wsdl_object_of_type('Weight')
    package_weight.Units = uom_mapper.get(pkg.weight_uom)
    package_weight.Value = pkg.package_weight
    package.Weight = package_weight

    # Adding references as required by label evaluation process
    if track_doc.purpose == 'SOLD':
        po_no = frappe.get_value(track_doc.document, track_doc.document_name, "po_no")
        po_no = re.sub(r'[^a-zA-Z0-9]', '', po_no)
        po_no = po_no[:16]
        si_no = track_doc.document_name
        for ref, field in {"P_O_NUMBER": po_no, "INVOICE_NUMBER": si_no}.items():
            ref_data = shipment.create_wsdl_object_of_type('CustomerReference')
            ref_data.CustomerReferenceType = ref
            ref_data.Value = field
            package.CustomerReferences.append(ref_data)

    return package


def validate_fedex_shipping_response(shipment, package_id):
    msg = ''
    try:
        msg = shipment.response.Message
    except:
        pass
    if shipment.response.HighestSeverity == "SUCCESS":
        frappe.msgprint('Shipment is created successfully in Fedex service for package {0}.'. \
                        format(package_id))
    elif shipment.response.HighestSeverity in ["NOTE", "WARNING"]:
        frappe.msgprint('Shipment is created in Fedex service for package {0} with the following '
                        'message:\n{1}'.format(package_id, msg))
        show_notification(shipment)
    else:  # ERROR, FAILURE
        show_notification(shipment)
        frappe.throw('Creating of Shipment in Fedex service for package {0} failed.'.format(package_id))


def show_notification(shipment):
    for notification in shipment.response.Notifications:
        frappe.msgprint('Code: %s, %s' % (notification.Code, notification.Message))


def set_package_details(pkg, shipment_response, tracking_id):
    pkg.shipment_response = shipment_response
    pkg.tracking_id = tracking_id


def store_label(shipment, tracking_id, ps_doctype, ps_name):
    label_data = base64.b64decode(
        shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].Label.Parts[0].Image)
    store_file('FEDEX-ID-{0}.pdf'.format(tracking_id), label_data, ps_doctype, ps_name)
    if hasattr(shipment.response.CompletedShipmentDetail, 'ShipmentDocuments'):
        invoice_data = base64.b64decode(
            shipment.response.CompletedShipmentDetail.ShipmentDocuments[0].Parts[0].Image)
        store_file('COMMER-INV-{0}-{1}.pdf'.format(ps_name, tracking_id), invoice_data, ps_doctype, ps_name)


def store_file(file_name, image_data, ps_doctype, ps_name):
    frappe.msgprint(str(file_name))
    save_file(file_name, image_data, ps_doctype, ps_name, is_private=1)


def get_fedex_credentials(transporter_doc):
    from fedex.config import FedexConfig
    credentials = FedexConfig(key=transporter_doc.fedex_key,
                              password=transporter_doc.fedex_password,
                              account_number=transporter_doc.fedex_account_number,
                              meter_number=transporter_doc.fedex_meter_number,
                              use_test_server=transporter_doc.is_test_server)
    return credentials