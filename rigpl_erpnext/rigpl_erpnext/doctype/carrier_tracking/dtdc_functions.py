# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import json
import base64
from datetime import datetime
from frappe.utils.file_manager import save_file
uom_mapper = {"gm": "gm", "Kg": "kg"}


def dtdc_get_available_services(ctrack, cod=0):
    frm_add_doc = frappe.get_doc("Address", ctrack.from_address)
    to_add_doc = frappe.get_doc("Address", ctrack.to_address)
    frm_pincode = frm_add_doc.pincode
    to_pincode = to_add_doc.pincode
    url = frappe.get_value("Transporters", ctrack.carrier_name, "dtdc_service_validation_link")
    pincodes = {}
    pincodes["orgPincode"] = frm_pincode
    pincodes["desPincode"] = to_pincode
    reply = requests.post(url=url, json=pincodes)
    zip_resp = (reply.json()).get("ZIPCODE_RESP")[0]
    if zip_resp.get("SERVFLAG") == 'N':
        all_service = 0
    else:
        pin_resp = (reply.json()).get("PIN_CITY", "No Service")
        if pin_resp != "No Service":
            all_service = 1
        else:
            all_service = 0

    if zip_resp.get("SERV_COD") == 'N':
        cod_service = 0
    else:
        cod_service = 1

    if cod==1 and cod_service == 0:
        frappe.throw("COD Service is Not Available at {}".format(to_pincode))
    if all_service == 1:
        message = ""
        for d in pin_resp:
            message += "PIN Code: " + d.get("PIN") +  " Type of Services: " + d.get("PARTIALSERV_AREA_AND_CITY") + "\n"
        frappe.msgprint(message)
    else:
        frappe.throw("No Service Available between PIN Codes {} and {}".format(frm_pincode, to_pincode))


def dtdc_shipment_booking(track_doc):
    dtdc_get_available_services(track_doc)
    trans_doc = frappe.get_doc('Transporters', track_doc.carrier_name)
    booking_json = get_dtdc_booking_data(track_doc, trans_doc)
    book_reply = post_dtdc_booking_request(booking_json, trans_doc)
    update_ctrack_doc(json_reply=book_reply, ctrack_doc=track_doc)
    dtdc_get_pdf(track_doc.awb_number, track_doc)


def dtdc_get_pdf(awb_no, track_doc):
    url = frappe.get_value("Transporters", track_doc.carrier_name, "dtdc_base_link")
    api_key = frappe.get_value("Transporters", track_doc.carrier_name, "api_key")
    api_key_dict = {}
    awb_dict = {}
    awb_dict["reference_number"] = awb_no
    api_key_dict["api-key"] = api_key
    pdf_url = url + "label/multipiece/"
    pdf_reply = requests.post(url=pdf_url, headers=api_key_dict, json=awb_dict)
    if (pdf_reply.json()).get("status") == "OK":
        pdf_data = (pdf_reply.json()).get("data")
        for label in pdf_data:
            label_data = base64.b64decode(label.get("label"))
            file_name = "DTDC-{}.pdf".format(label.get("reference_number"))
            save_file(file_name, label_data, track_doc.doctype, track_doc.name, is_private=1)
    else:
        frappe.throw("Error in Getting PDF for {}".format(track_doc.name))


def update_ctrack_doc(json_reply, ctrack_doc):
    if json_reply.get("status") == "OK":
        booking_data = json_reply.get("data")[0]
        if booking_data.get("success") == 1:
            ctrack_doc.awb_number = booking_data.get("reference_number")
            ctrack_doc.status = "Booked"
            update_package_tracking_id(ctrack_doc, booking_data.get("pieces"))
        else:
            frappe.throw(str(booking_data))
    else:
        frappe.throw("Unable to Book Shipment for {}. Reply is {}".format(ctrack_doc.name, str(json_reply)))


def update_package_tracking_id(ct_doc, pcs_list):
    if len(pcs_list) == len(ct_doc.shipment_package_details):
        for row in ct_doc.shipment_package_details:
            for pkg_no in range(0, len(pcs_list)):
                if row.idx == pkg_no + 1:
                    row.tracking_id = pcs_list[pkg_no].get("reference_number")
    else:
        frappe.throw("No of Packages does not Match in {}".format(ct_doc))


def post_dtdc_booking_request(booking_json, trans_doc):
    base_url = get_dtdc_base_url(trans_doc, type='base')
    booking_url = base_url + 'softdata'
    api_key = trans_doc.api_key
    booking_json = json.dumps(booking_json, indent=4)
    booking_json = json.loads(booking_json)
    api_key_dict = {}
    api_key_dict["api-key"] = api_key
    api_key_dict = json.dumps(api_key_dict, indent=4)
    api_key_dict = json.loads(api_key_dict)
    reply = requests.post(url=booking_url, json=booking_json, headers=api_key_dict)
    return reply.json()


def get_dtdc_booking_data(t_doc, tpt_doc):
    bk_json = {}
    booking_json = {}
    bk_json["customer_code"] = tpt_doc.dtdc_customer_code
    bk_json["service_type_id"] = tpt_doc.dtdc_service_id
    if t_doc.is_inward == 1:
        bk_json["consignment_type"] = "reverse"
    else:
        bk_json["consignment_type"] = "forward"
    bk_json["commodity_id"] = "Cutting Tools"
    bk_json["cod_amount"] = 0
    bk_json["load_type"] = "NON-DOCUMENT" # "DOCUMENT"
    bk_json["weight_unit"] = uom_mapper.get(t_doc.weight_uom)
    bk_json["weight"] = t_doc.total_weight
    bk_json["declared_value"] = t_doc.amount
    bk_json["num_pieces"] = t_doc.total_handling_units
    bk_json["is_risk_surcharge_applicable"] = "false"
    if t_doc.document == 'Sales Invoice':
        # si_doc = frappe.get_doc(t_doc.document, t_doc.document_name)
        bk_json["invoice_number"] = t_doc.document_name
    bk_json["customer_reference_number"] = t_doc.name
    bk_json["origin_details"] = get_dtdc_address(t_doc.from_address)
    bk_json["destination_details"] = get_dtdc_address(t_doc.to_address)
    bk_json["pieces_detail"] = get_dtdc_packages(t_doc)
    booking_json["consignments"] = [bk_json]
    return booking_json


def get_dtdc_packages(track_doc):
    pkgs = []
    for pkg in track_doc.shipment_package_details:
        pkg_dict = {}
        pkg_doc = frappe.get_doc("Shipment Package", pkg.shipment_package)
        pkg_dict["description"] = "Cutting Tools"
        pkg_dict["declared_value"] = track_doc.amount
        pkg_dict["weight"] = pkg.package_weight
        pkg_dict["height"] = pkg_doc.height
        pkg_dict["length"] = pkg_doc.length
        pkg_dict["width"] = pkg_doc.width
        pkgs.append(pkg_dict.copy())
    return pkgs


def get_dtdc_address(add_name):
    add_json = {}
    add_doc = frappe.get_doc('Address', add_name)
    add_json["pincode"] = add_doc.pincode
    add_json["name"] = add_doc.address_title
    add_json["phone"] = add_doc.phone
    add_json["address_line_1"] = add_doc.address_line1
    add_json["address_line_2"] = add_doc.address_line2
    add_json["city"] = add_doc.city
    add_json["state"] = add_doc.state
    return add_json


def get_tracking_from_dtdc(track_doc):
    trans_doc = frappe.get_doc('Transporters', track_doc.carrier_name)
    track_token = dtdc_track_auth_token(trans_doc)
    track_url = dtdc_get_tracking_url(trans_doc)
    track_response = dtdc_get_tracking_response(track_doc, url=track_url, token=track_token)
    dtdc_update_tracking(track_doc, track_response)


def dtdc_get_tracking_response(track_doc, url, token):
    json_data, header = dtdc_get_track_json(track_doc, token=token)
    json_data = json.loads(json_data)
    trk_resp = requests.post(url=url, json=json_data, headers=header)
    return trk_resp.json()


def dtdc_update_tracking(doc, json_data):
    if json_data.get("statusCode") == 200:
        header = json_data.get("trackHeader")
        doc.ship_to_city = header.get("strDestination")
        if header.get("strBookedDate") != "" and header.get("strBookedTime") != "":
            pdt = header.get("strBookedDate") + " " + header.get("strBookedTime")
        else:
            pdt = ""
        if pdt != "":
            for fmt in ("%d%m%Y %H:%M:%S", "%d%m%Y %H:%M"):
                try:
                    pickup_date_time = datetime.strptime(pdt, fmt)
                except:
                    print("Error in Format for Pickup Date")
        if header.get("strExpectedDeliveryDate") != "":
            exp_delivery_date = datetime.strptime(header.get("strExpectedDeliveryDate"), "%d%m%Y")
        else:
            exp_delivery_date = datetime.strptime("01011900", "%d%m%Y")
        doc.pickup_date = pickup_date_time
        doc.expected_delivery_date = exp_delivery_date.date()
        doc.recipient = header.get("strRemarks") + " " + header.get("strStatusRelName")
        if header.get("strStatus") == 'Delivered':
            doc.status = 'Delivered'
            doc.delivery_date_time = datetime.strptime((header.get("strStatusTransOn") +
                                                       header.get("strStatusTransTime")), '%d%m%Y%H%M')
        else:
            doc.status = 'In Transit'
        scans = []
        if json_data.get("trackDetails"):
            for scan in json_data.get("trackDetails"):
                scan_dict = {}
                scan_dict["time"] = datetime.strptime((scan.get("strActionDate") +
                                                       scan.get("strActionTime")), '%d%m%Y%H%M')
                scan_dict["location"] = 'Frm: ' + scan.get("strOrigin") + ' To: ' + scan.get("strDestination")
                status_detail = scan.get("strCode") + ': ' + scan.get("strAction") + "-" + scan.get("strManifestNo") + \
                                " " + scan.get("sTrRemarks")
                if len(status_detail) > 140:
                    status_detail = status_detail[:140]
                scan_dict["status_detail"] = status_detail
                scans.append(scan_dict.copy())
            doc.scans = []
            for scan in scans:
                doc.append("scans", scan)
        doc.save(ignore_permissions=True)
    else:
        frappe.msgprint('Error {}'.format(str(json_data.get("errorDetails"))))


def dtdc_get_track_json(track_doc, token):
    json_data = {}
    header = {}
    json_data["trkType"] = "cnno" #cnno or reference
    json_data["strcnno"] = track_doc.awb_number
    json_data["addtnlDtl"] = "Y"
    header["X-Access-Token"] = token
    json_data = json.dumps(json_data)
    return json_data, header


def dtdc_track_auth_token(trans_doc):
    # trk_uname = trans_doc.dtdc_tracking_username
    url = get_dtdc_base_url(trans_doc, type='track')
    auth = get_dtdc_authentication(trans_doc, type='track')
    full_url = url + auth
    token_resp = requests.get(full_url)
    token = token_resp.text
    # token = (token_resp.text).split(':')[1]
    return token


def get_dtdc_authentication(trans_doc, type='base'):
    if type == 'base':
        frappe.throw("Get DTDC Base Authentication")
    else:
        trk_uname = trans_doc.dtdc_tracking_username
        trk_pass = trans_doc.dtdc_tracking_password
        return 'api/dtdc/authenticate?username=' + trk_uname + '&password=' + trk_pass


def get_dtdc_base_url(trans_doc, type='base'):
    if type == 'base':
        return trans_doc.dtdc_base_link
    else:
        return trans_doc.dtdc_tracking_base_link


def dtdc_get_tracking_url(trans_doc):
    base_url = get_dtdc_base_url(trans_doc, type='track')
    full_url = base_url + 'rest/JSONCnTrk/getTrackDetails'
    return full_url
