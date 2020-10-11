# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import re
import json
import frappe
import requests
from datetime import datetime, date
from ..doctype.carrier_tracking.fedex_functions import get_tracking_from_fedex
from ..doctype.carrier_tracking.dtdc_functions import get_tracking_from_dtdc


def update_delivery_date_time():
    ctrack_dict = frappe.db.sql("""SELECT ct.name FROM `tabCarrier Tracking` ct WHERE ct.status = 'Delivered' 
    AND ct.docstatus !=2 AND ct.status_code = 'DL' AND ct.delivery_date_time IS NULL 
    ORDER BY ct.creation ASC""", as_dict=1)
    sno=1
    for ct in ctrack_dict:
        ct_doc = frappe.get_doc('Carrier Tracking', ct.name)
        print(str(sno) + ". " + ct.name + " is being Updated")
        sno +=1
        get_tracking_from_fedex(ct_doc)
        frappe.db.commit()

def update_costing_bypass():
    bypass_ct = frappe.db.sql("""SELECT ct.name FROM `tabCarrier Tracking` ct WHERE ct.docstatus<2 
        AND ct.document = 'Sales Invoice' ORDER BY ct.creation DESC""")
    sno = 0
    for ct in bypass_ct:
        ctrack_doc = frappe.get_doc("Carrier Tracking", ct[0])
        trans_doc = frappe.get_doc('Transporters', ctrack_doc.carrier_name)
        cost_high = courier_charges_validation(ctrack_doc, trans_doc, backend=1)
        if cost_high == 1 and ctrack_doc.bypass_courier_charged_check==0 and ctrack_doc.status != "" \
                and ctrack_doc.status != "Not Booked":
            print('{}. Setting Bypass Courier Charges Check for {}'.format(str(sno+1), ct[0]))
            ctrack_doc.bypass_courier_charged_check = 1
            ctrack_doc.save()
            sno += 1


def update_ctrack_from_invoice():
    ct_list = frappe.db.sql("""SELECT ct.name, ct.document_name FROM `tabCarrier Tracking` ct 
        WHERE ct.docstatus !=2 AND ct.document = 'Sales Invoice' AND ct.invoice_integrity = 0 
        ORDER BY ct.creation DESC""", as_list=1)
    #AND DATEDIFF(CURDATE(),ct.creation) < 180
    ct_sno = 0
    si_sno = 0
    man_sno = 0
    for ct in ct_list:
        ctrack_doc = frappe.get_doc('Carrier Tracking', ct[0])
        trans_doc = frappe.get_doc('Transporters', ctrack_doc.carrier_name)

        si_doc = frappe.get_doc('Sales Invoice', ct[1])
        if ctrack_doc.awb_number == si_doc.lr_no:
            print("Updating {} and making Invoice Integrity = 1".format(ctrack_doc.name))
            ctrack_doc.invoice_integrity = 1
            ctrack_doc.save()
        else:
            # If the data is not same in Ctrack and Sales Invoice
            # then we need to check if Ctrack = NA or "" or it could be SI is NA or ""
            # if both have value then do the change manually.
            if ctrack_doc.awb_number == "NA" or ctrack_doc.awb_number == "" or ctrack_doc.awb_number is None:
                ctrack_awb = 0
            else:
                ctrack_awb = 1
            if si_doc.lr_no == "NA" or si_doc.lr_no == "" or si_doc.lr_no is None:
                si_awb = 0
            else:
                si_awb = 1
            if ctrack_awb == 0 and si_awb == 1:
                if ctrack_doc.docstatus == 0:
                    ctrack_doc.awb_number = si_doc.lr_no
                else:
                    frappe.db.set_value('Carrier Tracking', ctrack_doc.name, 'awb_number', si_doc.lr_no)
                print(str(si_sno + 1) + ". Update from SI. SI AWB= " + si_doc.lr_no + " but Ctrack AWB= " +
                      str(ctrack_doc.awb_number))
                cost_high = courier_charges_validation(ctrack_doc, trans_doc, backend=1)
                if cost_high == 1:
                    ctrack_doc.bypass_courier_charged_check = 1
                if ctrack_doc.docstatus == 0:
                    ctrack_doc.save()
                si_sno += 1
            elif ctrack_awb == 1 and si_awb == 0:
                print(str(ct_sno+1) + ". Update from Ctrack. Ctrack AWB= " + ctrack_doc.awb_number + " but SI AWB= "
                      + str(si_doc.lr_no) + " SI# " + si_doc.name)
                si_doc.lr_no = ctrack_doc.awb_number
                si_doc.save()
                ct_sno += 1
            elif ctrack_awb == 1 and si_awb == 1:
                #Both CTRACK and SI have different AWB now check if the AWB is same without SPACES.
                if re.sub('[^A-Za-z0-9]+', '', str(ctrack_doc.awb_number)) == \
                        re.sub('[^A-Za-z0-9]+', '', str(si_doc.lr_no)):
                    print ("Updated SI# " + si_doc.name + " from CTRACK# " + ctrack_doc.name + " as both were"
                                                                                               " same without spaces")
                    si_doc.lr_no = re.sub('[^A-Za-z0-9]+', '', str(si_doc.lr_no))
                    si_doc.save()
                else:
                    print(str(man_sno+1) + ". SI# " + si_doc.name + " and CTRACK# " + ctrack_doc.name +
                      " have different AWB")
                    man_sno += 1


def send_bulk_tracks():
    # Pause of 5seconds for sending data means 720 shipment data per hour can be sent
    # Get the list of all Shipments which are not posted
    unposted = frappe.db.sql("""SELECT ct.name FROM `tabCarrier Tracking` ct, `tabTransporters` tpt
        WHERE ct.posted_to_shipway = 0 AND ct.docstatus != 2 AND ct.awb_number <> "NA"
        AND ct.awb_number != "" AND tpt.track_on_shipway = 1 AND ct.carrier_name = tpt.name
        ORDER BY ct.creation DESC """, as_list=1)
    for tracks in unposted:
        track_doc = frappe.get_doc("Carrier Tracking", tracks[0])
        trans_doc = frappe.get_doc("Transporters", track_doc.carrier_name)
        if trans_doc.fedex_credentials == 1 or trans_doc.fedex_tracking_only == 1:
            print(("Direct Fedex Booking for {}. Not Posting to Shipway").format(track_doc.name))
        else:
            days_diff = (datetime.today().date() - track_doc.modified.date()).days
            if 1 < days_diff < 20:
                print('Pushed ' + track_doc.name + ' Older than 1 days. Total Days Old = ' + str(days_diff))
                pushOrderData(track_doc)
                frappe.db.commit()
            elif days_diff >= 20:
                print('NOT POSTING ' + track_doc.name + ' since Data is Now STALE with ' + str(days_diff) + " Days Old")
            else:
                print('NOT POSTING ' + track_doc.name + " " + \
                      str(track_doc.creation) + ' Not Old Enough')


def get_all_ship_data():
    # Pause of 5seconds for sending data means 720 shipment data per hour can be sent
    # Get the list of all Shipments which are POSTED and NOT DELIVERED
    pending_ships = frappe.db.sql("""SELECT ctrack.name as name, tpt.fedex_credentials as cred, 
        ctrack.creation as creation, tpt.fedex_tracking_only as tracking_only, ctrack.modified as modified
        FROM `tabCarrier Tracking` ctrack, `tabTransporters` tpt 
        WHERE (ctrack.posted_to_shipway = 1 OR tpt.fedex_credentials = 1 or tpt.fedex_tracking_only = 1) 
        AND ctrack.manual_exception_removed = 0 AND ctrack.docstatus != 2 AND tpt.name = ctrack.carrier_name 
        AND ctrack.status != "Delivered" 
        AND ctrack.awb_number != "NA" AND ctrack.awb_number != "" ORDER BY ctrack.creation DESC """, as_dict=1)
    sno = 0
    for tracks in pending_ships:
        days_diff = (datetime.today().date() - tracks.creation.date()).days
        last_update_hrs = (datetime.now() - tracks.modified).seconds/3600
        if (tracks.cred == 1 or tracks.tracking_only == 1) and days_diff < 150:
            # Get from Fedex only if less than 150 days old
            if last_update_hrs > 6:
                print("{}. Getting Tracking for {} from Fedex".format(str(sno+1), tracks.name))
                track_doc = frappe.get_doc("Carrier Tracking", tracks.name)
                getOrderShipmentDetails(track_doc)
            else:
                print("{}. Fedex Tracking was updated less than 6 hrs ago hence skipping {}".
                      format(str(sno+1), tracks.name))
        elif (tracks.cred == 0 and tracks.tracking_only == 0) and days_diff < 60:
            # Get from Shipway only less than 60 days old shipments
            if last_update_hrs > 6:
                print("{}. Getting Tracking for {} from Shipway".format(str(sno+1), tracks.name))
                track_doc = frappe.get_doc("Carrier Tracking", tracks.name)
                getOrderShipmentDetails(track_doc)
            else:
                print("{}. Shipway Tracking was updated less than 6 hrs ago hence skipping {}".
                      format(str(sno + 1), tracks.name))
        #track_doc.flags.ignore_permissions = True
        sno += 1

        frappe.db.commit()


def pushOrderData(track_doc):
    # First check if the AWB for the Same Shipper is there is Shipway if its there then
    trans_doc = frappe.get_doc('Transporters', track_doc.carrier_name)
    if track_doc.get("__islocal") != 1 and track_doc.posted_to_shipway == 0 and trans_doc.track_on_shipway == 1:
        check_upload = post_to_shipway(track_doc)
        username, license_key = get_shipway_pass()
        if check_upload.get("status") != "Success":
            url = get_shipway_url() + "pushOrderData"
            post_data = {
                "username": username,
                "password": license_key,
                "carrier_id": frappe.get_value("Transporters", track_doc.carrier_name,
                                               "shipway_id"),  # from transporters doc
                "awb": track_doc.awb_number,
                "order_id": track_doc.name,
                "first_name": "Rohit",
                "last_name": "Cutting Tools",
                "email": "gmail@gmail.com",
                "phone": "9999999999",
                "products": "N/A"
            }
            p_response = requests.get(url=url, verify=False, \
                                      data=json.dumps(post_data))
            post_response = json.loads(p_response.text)
            if post_response.get("status") == "Success":
                track_doc.status = "Shipment Data Uploaded"
                track_doc.posted_to_shipway = 1
                track_doc.save()
            else:
                track_doc.status = "Posting Issues"
                frappe.msgprint(("Some Issues in posting {0}").format(track_doc.name))
        else:
            track_doc.posted_to_shipway = 1
            track_doc.status = "Shipment Data Uploaded"
            track_doc.save()
    elif track_doc.posted_to_shipway == 1:
        frappe.msgprint("Already Posted to Shipway")
    elif trans_doc.track_on_shipway != 1:
        frappe.throw('{} for {} is Not Tracked on Shipway'.format(
            frappe.get_desk_link(track_doc.doctype, track_doc.name),
            frappe.get_desk_link(trans_doc.doctype, trans_doc.name)))


def getOrderShipmentDetails(track_doc):
    print("Processing Carrier Tracking #: " + track_doc.name)
    trans_doc = frappe.get_doc('Transporters', track_doc.carrier_name)
    shipway = 0
    fedex = 0
    dtdc = 0
    if trans_doc.fedex_credentials == 1 or trans_doc.fedex_tracking_only == 1:
        fedex = 1
    elif trans_doc.dtdc_credentials == 1 or trans_doc.dtdc_tracking_only == 1:
        dtdc = 1
    elif trans_doc.track_on_shipway == 1:
        shipway = 1
    if track_doc.get("__islocal") != 1 and track_doc.status != "Delivered":
        if shipway == 1:
            response = post_to_shipway(track_doc)
            track_doc.json_reply = str(response)

            if response.get("status") == "Success":
                track_doc.scans = []
                web_response = response.get("response")
                web_scans = web_response.get("scan")

                if web_response.get("current_status_code") == "DEL":
                    track_doc.status = "Delivered"
                    track_doc.docstatus = 1
                elif web_response.get("current_status_code") == "NFI":
                    track_doc.status = "No Information"
                elif web_response.get("current_status_code") in ("CAN", "UND"):
                    track_doc.docstatus = 1
                    track_doc.status = "Cancelled"
                else:
                    track_doc.status = "In Transit"
                if web_scans:
                    for scan in web_scans:
                        track_doc.append("scans", scan)

                track_doc.status_code = web_response.get("current_status_code")
                track_doc.pickup_date = web_response.get("pickupdate")
                track_doc.ship_to_city = web_response.get("to")
                #if web_response.get("awbno"):
                    #track_doc.awb_number = web_response.get("awbno")
                track_doc.recipient = web_response.get("recipient")
                if track_doc.status == "Delivered":
                    track_doc.delivery_date_time = web_response.get("time")
                else:
                    track_doc.delivery_date_time = None

                track_doc.save()
            else:
                track_doc.status = "Posting Error"
        elif fedex == 1:
            get_tracking_from_fedex(track_doc)
        elif dtdc == 1:
            get_tracking_from_dtdc(track_doc)
    elif track_doc.status == 'Delivered':
        frappe.msgprint(("{0} is Already Delivered").format(track_doc.name))


def post_to_shipway (track_doc):
    username, license_key = get_shipway_pass()
    url = get_shipway_url() + "getOrderShipmentDetails"
    request = {
        "username": username,
        "password": license_key,
        "order_id": track_doc.name
    }
    response = requests.get(url=url, verify=False, data=json.dumps(request))
    response_json = json.loads(response.text)
    return response_json


def get_shipway_url():
    return "https://shipway.in/api/"


def get_shipway_pass():
    shipway_settings = frappe.get_doc("Shipway Settings")
    username = shipway_settings.username
    license_key = shipway_settings.license_key

    return username, license_key


def courier_charges_validation(ct_doc, trans_doc, backend=0):
    cost_high = 0
    if trans_doc.max_percent_of_invoice_value is not None and ct_doc.shipment_cost is not None:
        if ct_doc.amount > 0:
            if ct_doc.shipment_cost / ct_doc.amount * 100 > trans_doc.max_percent_of_invoice_value:
                if ct_doc.purpose != "SOLD" and ct_doc.document != "Sales Invoice":
                    frappe.msgprint("Permissible Courier Cost is High. Make Sure you Charge Courier for "
                                    "Minimum Amount of {}".format(ct_doc.shipment_cost), title="Warning From Admin")
                elif ct_doc.purpose == "SOLD" and ct_doc.document == "Sales Invoice":
                    if ct_doc.courier_charged < ct_doc.shipment_cost and ct_doc.bypass_courier_charged_check != 1:
                        if backend == 0:
                            frappe.throw("Not Allowed. Courier Charged in Invoice {} is Lower than Cost "
                                         "of ₹ {} for {}".format(ct_doc.document_name, ct_doc.shipment_cost,
                                                                 ct_doc.name), "Fatal Error")
                        cost_high = 1
    return cost_high