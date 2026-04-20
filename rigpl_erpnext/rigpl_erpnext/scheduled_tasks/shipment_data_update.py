# Copyright (c) 2021, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
# -*- coding: utf-8 -*-


from __future__ import unicode_literals
import re
import json
import frappe
import requests
from datetime import datetime
from frappe.utils.background_jobs import enqueue
from ..doctype.carrier_tracking.fedex_functions import get_tracking_from_fedex
from ..doctype.carrier_tracking.dtdc_functions import get_tracking_from_dtdc


def update_delivery_date_time():
    """
    This function updates the delivery date and time in Delivered Carrier Tracking if missing
    """
    ctrack_dict = frappe.db.sql("""SELECT ct.name FROM `tabCarrier Tracking` ct
        WHERE ct.status = 'Delivered' AND ct.docstatus !=2 AND ct.status_code = 'DL'
        AND ct.delivery_date_time IS NULL
        ORDER BY ct.creation ASC""", as_dict=1)
    sno=1
    for ct in ctrack_dict:
        ct_doc = frappe.get_doc('Carrier Tracking', ct.name)
        print(str(sno) + ". " + ct.name + " is being Updated")
        sno +=1
        get_tracking_from_fedex(ct_doc)
        # Only commit after a batch or at the end
        if sno % 50 == 0:
            frappe.db.commit()
    frappe.db.commit()

def update_costing_bypass():
    """
    This function updates the costing bypass check for old carrier trackings where cost is over
    desired %age value of the Sales Invoice
    """
    bypass_ct = frappe.db.sql("""SELECT ct.name, ct.carrier_name, ct.bypass_courier_charged_check, ct.status 
        FROM `tabCarrier Tracking` ct WHERE ct.docstatus<2
        AND ct.document = 'Sales Invoice' ORDER BY ct.creation DESC""", as_dict=1)
    
    if not bypass_ct:
        return

    # Pre-fetch transporters
    carrier_names = list(set([t.carrier_name for t in bypass_ct]))
    transporters = frappe.get_all("Transporters", filters={"name": ["in", carrier_names]}, 
        fields=["name", "max_percent_of_invoice_value"])
    trans_map = {t.name: t for t in transporters}

    sno = 0
    for ct in bypass_ct:
        trans_doc = trans_map.get(ct.carrier_name)
        if not trans_doc:
            continue
            
        # We still need ctrack_doc for amount/shipment_cost if not in SQL
        # Let's add them to SQL instead
        ct_data = frappe.db.get_value("Carrier Tracking", ct.name, ["amount", "shipment_cost", "purpose", "document", "courier_charged", "document_name"], as_dict=1)
        
        # Merge data for validation
        ct.update(ct_data)

        cost_high = courier_charges_validation(ct, trans_doc, backend=1)
        if cost_high == 1 and ct.bypass_courier_charged_check==0 and \
                ct.status != "" and ct.status != "Not Booked":
            print('{}. Setting Bypass Courier Charges Check for {}'.format(str(sno+1), ct.name))
            frappe.db.set_value("Carrier Tracking", ct.name, "bypass_courier_charged_check", 1)
            sno += 1
        
        if sno > 0 and sno % 100 == 0:
            frappe.db.commit()
    frappe.db.commit()


def update_ctrack_from_invoice():
    """
    Updates the AWB no of Ctrack linked to Sales Invoices if not same or missing
    Applicable for old Ctracks
    """
    ct_list = frappe.db.sql("""SELECT ct.name, ct.document_name, ct.awb_number, ct.carrier_name, ct.docstatus, ct.invoice_integrity
        FROM `tabCarrier Tracking` ct
        WHERE ct.docstatus !=2 AND ct.document = 'Sales Invoice' AND ct.invoice_integrity = 0
        ORDER BY ct.creation DESC""", as_dict=1)
    
    if not ct_list:
        return

    # Bulk fetch transporters
    carrier_names = list(set([t.carrier_name for t in ct_list]))
    transporters = frappe.get_all("Transporters", filters={"name": ["in", carrier_names]}, 
        fields=["name", "max_percent_of_invoice_value"])
    trans_map = {t.name: t for t in transporters}

    # Bulk fetch Sales Invoices
    si_names = [ct.document_name for ct in ct_list]
    sales_invoices = frappe.get_all("Sales Invoice", filters={"name": ["in", si_names]}, fields=["name", "lr_no"])
    si_map = {si.name: si for si in sales_invoices}

    ct_sno, si_sno, man_sno = 0, 0, 0
    
    for ct in ct_list:
        trans_doc = trans_map.get(ct.carrier_name)
        si_doc = si_map.get(ct.document_name)
        
        if not trans_doc or not si_doc:
            continue

        if ct.awb_number == si_doc.lr_no:
            print("Updating {} and making Invoice Integrity = 1".format(ct.name))
            frappe.db.set_value("Carrier Tracking", ct.name, "invoice_integrity", 1)
        else:
            ctrack_awb = 1 if ct.awb_number not in ("NA", "", None) else 0
            si_awb = 1 if si_doc.lr_no not in ("NA", "", None) else 0

            if ctrack_awb == 0 and si_awb == 1:
                frappe.db.set_value('Carrier Tracking', ct.name, 'awb_number', si_doc.lr_no)
                print(f"{str(si_sno + 1)}. Update from SI. SI AWB= {si_doc.lr_no} but CTrack AWB = {ct.awb_number}")
                
                # We need to re-fetch some fields for courier_charges_validation since it expects a dict-like object
                full_ct_data = frappe.db.get_value("Carrier Tracking", ct.name, ["amount", "shipment_cost", "purpose", "document", "courier_charged", "document_name", "bypass_courier_charged_check"], as_dict=1)
                full_ct_data.update(ct)
                full_ct_data.awb_number = si_doc.lr_no # Update with new value for validation
                
                cost_high = courier_charges_validation(full_ct_data, trans_doc, backend=1)
                if cost_high == 1:
                    frappe.db.set_value("Carrier Tracking", ct.name, "bypass_courier_charged_check", 1)
                
                si_sno += 1
            elif ctrack_awb == 1 and si_awb == 0:
                print(f"{str(ct_sno+1)}. Update from CTrack. CTrack AWB= {ct.awb_number} but SI AWB= {si_doc.lr_no} SI# {si_doc.name}")
                frappe.db.set_value("Sales Invoice", si_doc.name, "lr_no", ct.awb_number)
                ct_sno += 1
            elif ctrack_awb == 1 and si_awb == 1:
                if re.sub('[^A-Za-z0-9]+', '', str(ct.awb_number)) == \
                        re.sub('[^A-Za-z0-9]+', '', str(si_doc.lr_no)):
                    print(f"Updated SI# {si_doc.name} from CTrack# {ct.name} as both were same without spaces")
                    frappe.db.set_value("Sales Invoice", si_doc.name, "lr_no", re.sub('[^A-Za-z0-9]+', '', str(si_doc.lr_no)))
                else:
                    print(f"{str(man_sno+1)}. SI# {si_doc.name} and CTrack# {ct.name} have different AWB")
                    man_sno += 1
        
        if (ct_sno + si_sno + man_sno) % 100 == 0:
            frappe.db.commit()
    frappe.db.commit()


def send_bulk_tracks():
    """
    Sends CTracks in Bulk to Shipway for Carriers where there is no direct API Access
    """
    unposted = frappe.db.sql("""SELECT ct.name, ct.carrier_name, ct.modified, ct.creation, ct.awb_number 
        FROM `tabCarrier Tracking` ct, `tabTransporters` tpt
        WHERE ct.posted_to_shipway = 0 AND ct.docstatus != 2 AND ct.awb_number <> "NA"
        AND ct.awb_number != "" AND tpt.track_on_shipway = 1 AND ct.carrier_name = tpt.name
        ORDER BY ct.creation DESC """, as_dict=1)
    
    if not unposted:
        return

    # Bulk fetch transporters to avoid multiple get_doc calls
    carrier_names = list(set([t.carrier_name for t in unposted]))
    transporters = frappe.get_all("Transporters", filters={"name": ["in", carrier_names]}, 
        fields=["name", "fedex_credentials", "fedex_tracking_only", "dtdc_tracking_only", "dtdc_credentials", "track_on_shipway", "shipway_id"])
    trans_map = {t.name: t for t in transporters}

    for tracks in unposted:
        trans_doc = trans_map.get(tracks.carrier_name)
        if not trans_doc:
            continue
            
        if trans_doc.fedex_credentials == 1 or trans_doc.fedex_tracking_only == 1 or \
                trans_doc.dtdc_tracking_only == 1 or trans_doc.dtdc_credentials == 1:
            print(("Direct Fedex/DTDC Booking for {}. Not Posting to Shipway").format(tracks.name))
        else:
            days_diff = (datetime.today().date() - tracks.modified.date()).days
            if 1 < days_diff < 20:
                print(f"Pushed {tracks.name} Older than 1 Days. Total Days Old = {str(days_diff)}")
                
                # Manual doc created from dict to avoid get_doc if possible
                # But pushOrderData does its own get_doc, let's optimize that too if needed
                track_doc = frappe.get_doc("Carrier Tracking", tracks.name)
                pushOrderData(track_doc, trans_doc)
                frappe.db.commit()
            elif days_diff >= 20:
                print(f"Not Posting {tracks.name} since Data is now STALE with {str(days_diff)} Days Old")
            else:
                print(f"Not Posting {tracks.name} Created On: {str(tracks.creation)} since its Not Old Enough")



def enqueue_get_ship_data():
    """
    Enqueues the Shipment Data for Getting the Tracking. Enqueue basically avoids the standard
    timeout which is of 300 seconds
    """
    enqueue(get_all_ship_data, queue="long", timeout=1500)


def get_all_ship_data():
    """
    Gets the Shipment Tracking of all the Shipments which are booked but not delivered
    Also checks if the shipment has not been manually disabled for tracking.
    """
    pending_ships = frappe.db.sql("""SELECT ctrack.name as name, tpt.fedex_credentials as fed_cred,
        tpt.dtdc_credentials as dtdc_cred, tpt.dtdc_tracking_only as dtdc_track,
        ctrack.creation as creation, tpt.fedex_tracking_only as fed_track, ctrack.modified as modified,
        ctrack.carrier_name
        FROM `tabCarrier Tracking` ctrack, `tabTransporters` tpt
        WHERE (ctrack.posted_to_shipway = 1 OR tpt.fedex_credentials = 1 or tpt.fedex_tracking_only = 1
        OR tpt.dtdc_credentials = 1 OR tpt.dtdc_tracking_only = 1)
        AND ctrack.manual_exception_removed = 0 AND ctrack.docstatus != 2 AND tpt.name = ctrack.carrier_name
        AND ctrack.status != "Delivered"
        AND ctrack.awb_number != "NA" AND ctrack.awb_number != ""
        ORDER BY ctrack.creation ASC """, as_dict=1)
    
    if not pending_ships:
        return

    # Bulk fetch transporters
    carrier_names = list(set([t.carrier_name for t in pending_ships]))
    transporters = frappe.get_all("Transporters", filters={"name": ["in", carrier_names]}, 
        fields=["name", "fedex_credentials", "fedex_tracking_only", "dtdc_tracking_only", "dtdc_credentials", "track_on_shipway"])
    trans_map = {t.name: t for t in transporters}

    sno = 0
    now_dt = datetime.now()
    today_date = now_dt.date()

    for tracks in pending_ships:
        days_diff = (today_date - tracks.creation.date()).days
        last_update_hrs = (now_dt - tracks.modified).total_seconds()/3600
        
        fedex = tracks.fed_track or tracks.fed_cred
        dtdc = tracks.dtdc_track or tracks.dtdc_cred
        
        track_name = "Fedex" if fedex else ("DTDC" if dtdc else "Shipway")
        
        should_update = False
        if (tracks.fed_cred == 1 or tracks.fed_track == 1 or tracks.dtdc_cred == 1 or
                tracks.dtdc_track == 1) and 150 > days_diff > 1:
            if last_update_hrs > 6:
                should_update = True
        elif (tracks.fed_cred == 0 and tracks.fed_track == 0 and tracks.dtdc_cred == 0 and
                tracks.dtdc_track == 0) and 2 < days_diff < 60:
            if last_update_hrs > 6:
                should_update = True
        
        if should_update:
            print(f"{str(sno+1)}. Getting Tracking for {tracks.name} from {track_name}")
            track_doc = frappe.get_doc("Carrier Tracking", tracks.name)
            trans_doc = trans_map.get(tracks.carrier_name)
            try:
                # Passing trans_doc to avoid another get_doc inside getOrderShipmentDetails
                getOrderShipmentDetails(track_doc, trans_doc)
            except Exception as e:
                print(f"Error for {tracks.name}: {e}")
            
            sno += 1
            if sno % 20 == 0:
                frappe.db.commit()
    
    frappe.db.commit()


def pushOrderData(track_doc, trans_doc=None):
    """
    Purshes a Carrier Tracking to Shipway for all non direct API
    """
    if not trans_doc:
        trans_doc = frappe.get_doc('Transporters', track_doc.carrier_name)

    if track_doc.get("__islocal") != 1 and track_doc.posted_to_shipway == 0 and \
            trans_doc.track_on_shipway == 1:
        
        # Optimization: Fetch Shipway settings only once if needed, or use cached value
        username, license_key = get_shipway_pass()
        
        check_upload = post_to_shipway(track_doc)
        if check_upload.get("status") != "Success":
            url = get_shipway_url() + "pushOrderData"
            post_data = {
                "username": username,
                "password": license_key,
                "carrier_id": trans_doc.shipway_id,
                "awb": track_doc.awb_number,
                "order_id": track_doc.name,
                "first_name": "Rohit",
                "last_name": "Cutting Tools",
                "email": "gmail@gmail.com",
                "phone": "9999999999",
                "products": "N/A"
            }
            p_response = requests.get(url=url, verify=False,
                                      data=json.dumps(post_data))
            post_response = json.loads(p_response.text)
            if post_response.get("status") == "Success":
                frappe.db.set_value("Carrier Tracking", track_doc.name, {
                    "status": "Shipment Data Uploaded",
                    "posted_to_shipway": 1
                })
            else:
                frappe.db.set_value("Carrier Tracking", track_doc.name, "status", "Posting Issues")
                # frappe.msgprint(("Some Issues in posting {0}").format(track_doc.name))
        else:
            frappe.db.set_value("Carrier Tracking", track_doc.name, {
                "status": "Shipment Data Uploaded",
                "posted_to_shipway": 1
            })
    elif track_doc.posted_to_shipway == 1:
        print(f"Already Posted to Shipway: {track_doc.name}")
    elif trans_doc.track_on_shipway != 1:
        print(f"Transporter {trans_doc.name} not tracked on Shipway")


def getOrderShipmentDetails(track_doc, trans_doc=None):
    """
    Gets tracking for a Particular Carrier Tracking from respecting Carrier
    """
    print("Processing Carrier Tracking #: " + track_doc.name)
    if not trans_doc:
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


def post_to_shipway(track_doc):
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
    shipway_settings = frappe.get_cached_doc("Shipway Settings")
    username = shipway_settings.username
    license_key = shipway_settings.license_key

    return username, license_key


def courier_charges_validation(ct_doc, trans_doc, backend=0):
    """
    Checks if courier cost is within the allowed %age for invoice value. Suppose if you allow 2%
    as max courier charges without charging so if the cost of courier is like 3% and courier is not
    charged it would return cost_high=1
    """
    cost_high = 0
    if trans_doc.max_percent_of_invoice_value is not None and ct_doc.shipment_cost is not None:
        if ct_doc.amount > 0:
            if ct_doc.shipment_cost / ct_doc.amount * 100 > trans_doc.max_percent_of_invoice_value:
                if ct_doc.purpose != "SOLD" and ct_doc.document != "Sales Invoice":
                    frappe.msgprint(f"Permissible Courier Cost is High. Make sure you charge"
                        f" courier for Minumum Amount of {ct_doc.shipment_cost}",
                        title="Warning From Admin")
                elif ct_doc.purpose == "SOLD" and ct_doc.document == "Sales Invoice":
                    if ct_doc.courier_charged < ct_doc.shipment_cost and \
                            ct_doc.bypass_courier_charged_check != 1:
                        if backend == 0:
                            frappe.throw("Not Allowed. Courier Charged in Invoice "
                                f"{ct_doc.document_name} is Lower than Cost of ₹ "
                                f"{ct_doc.shipment_cost} for {ct_doc.name}", title="Fatal Error")
                        cost_high = 1
    return cost_high
