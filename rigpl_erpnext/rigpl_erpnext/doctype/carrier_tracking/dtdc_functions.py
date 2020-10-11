# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import json
from datetime import datetime
uom_mapper = {"gm": "gm", "Kg": "kg"}


def dtdc_shipment_booking(track_doc):
    trans_doc = frappe.get_doc('Transporters', track_doc.carrier_name)
    booking_json = get_dtdc_booking_data(track_doc, trans_doc)
    book_reply = post_dtdc_booking_request(booking_json, trans_doc)
    frappe.throw(str(booking_json))


def post_dtdc_booking_request(booking_json, trans_doc):
    base_url = get_dtdc_base_url(trans_doc, type='base')
    api_key = trans_doc.api_key
    api_key_dict = {}
    api_key_dict["api-key"] = api_key
    auth_reply = dtdc_auth_check(api_key_dict, base_url)
    reply = requests.post(url=base_url, json=booking_json)
    frappe.throw(str(reply.text))


def dtdc_auth_check(api_dict, url):
    api_dict = json.dumps(api_dict)
    auth_reply = requests.post(url=url, data=api_dict)
    frappe.throw(auth_reply.text)


def get_dtdc_booking_data(t_doc, tpt_doc):
    bk_json = {}
    bk_json["customer_code"] = tpt_doc.dtdc_customer_code
    bk_json["origin_details"] = get_dtdc_address(t_doc.from_address)
    bk_json["destination_details"] = get_dtdc_address(t_doc.to_address)
    bk_json["load_type"] = "NON-DOCUMENT" # "DOCUMENT"
    bk_json["weight_unit"] = uom_mapper.get(t_doc.weight_uom)
    bk_json["weight"] = t_doc.total_weight
    bk_json["service_type_id"] = tpt_doc.dtdc_service_id
    bk_json["declared_value"] = t_doc.amount
    bk_json["num_pieces"] = t_doc.total_handling_units
    bk_json["pieces_detail"] = get_dtdc_packages(t_doc)
    if t_doc.document == 'Sales Invoice':
        si_doc = frappe.get_doc(t_doc.document, t_doc.document_name)
        bk_json["invoice_number"] = t_doc.document_name
        bk_json["customer_reference_number"] = si_doc.po_no
    return bk_json


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
    dtdc_update_tracking(track_doc, track_response.json())


def dtdc_get_tracking_response(track_doc, url, token):
    json_data, header = dtdc_get_track_json(track_doc, token=token)
    json_data = json.loads(json_data)
    frappe.msgprint(url)
    frappe.msgprint(str(json_data))
    trk_resp = requests.post(url=url, json=json_data, headers=header)
    frappe.throw(str(trk_resp.text))
    dtdc_update_tracking(track_doc, json_data)
    return trk_resp.json()


def dtdc_update_tracking(doc, json_data):
    if json_data.statusCode == 200:
        header = json_data.trackHeader
        doc.ship_to_city = header.strDestination
        doc.recipient = header.strRemarks + " " + header.strStatusRelName
        if json_data.strStatus == 'Delivered':
            doc.status = 'Delivered'
            doc.delivery_datetime = datetime.strptime((json_data.strStatusTransOn + json_data.strStatusTransTime),
                                                      '%d%M%Y%H%M')
        else:
            doc.status = 'In Transit'
        scans = []
        for scan in json_data.trackDetails:
            scan_dict = {}
            scan_dict["time"] = datetime.strptime((scan.strActionDate + scan.strActionTime), '%d%M%Y%H%M')
            scan_dict["location"] = 'Frm: ' + scan.strOrigin + ' To: ' + scan.strDestination
            scan_dict["status_detail"] = scan.strCode + ': ' + scan.strAction + "-" + scan.strManifestNo + " " + \
                                         scan.sTrRemarks
            scans.append(scan_dict.copy())
        for scan in scans:
            doc.append("scans", scan)
        doc.save(ignore_permissions=True)
    else:
        frappe.throw('Error {}'.format(json_data.errorDetails))


def dtdc_get_track_json(track_doc, token):
    json_data = {}
    header = {}
    json_data["trkType"] = 'cnno' #cnno or reference
    json_data["strcnno"] = track_doc.awb_number
    json_data["addtnlDtl"] = 'N'
    header["X-Access-Token"] = token
    json_data = json.dumps(json_data)
    return json_data, header


def dtdc_track_auth_token(trans_doc):
    # trk_uname = trans_doc.dtdc_tracking_username
    url = get_dtdc_base_url(trans_doc, type='track')
    auth = get_dtdc_authentication(trans_doc, type='track')
    full_url = url + auth
    # frappe.throw(full_url)
    token_resp = requests.get(full_url)
    token = (token_resp.text).split(':')[1]
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
