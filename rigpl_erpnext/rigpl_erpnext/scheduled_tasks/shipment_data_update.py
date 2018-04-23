# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import requests
from datetime import datetime, date


def send_bulk_tracks():
	#Pause of 5seconds for sending data means 720 shipment data per hour can be sent
	#Get the list of all Shipments which are not posted
	unposted = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` 
		WHERE posted_to_shipway = 0 AND docstatus = 0 
		ORDER BY creation DESC """, as_list=1)
	for tracks in unposted:
		track_doc = frappe.get_doc("Carrier Tracking", tracks[0])
		trans_doc = frappe.get_doc("Transporters", track_doc.carrier_name)
		if trans_doc.fedex_credentials == 1:
			if track_doc.status == "Booked":
				if (datetime.today().date() - track_doc.modified.date()).days > 1:
					print('Pushed ' + track_doc.name + ' Older than 1 days')
					pushOrderData(track_doc)
					frappe.db.commit()
				else:
					print('NOT POSTING ' + track_doc.name + " " + \
						str(track_doc.creation) + ' Not Old Enough')
		else:
			if (datetime.today().date() - track_doc.modified.date()).days > 1:
				print('Pushed ' + track_doc.name + ' Older than 1 days')
				pushOrderData(track_doc)
				frappe.db.commit()
			else:
				print('NOT POSTING ' + track_doc.name + " " + \
					str(track_doc.creation) + ' Not Old Enough')

def get_all_ship_data():
	#Pause of 5seconds for sending data means 720 shipment data per hour can be sent
	#Get the list of all Shipments which are POSTED and NOT DELIVERED
	pending_ships = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` 
		WHERE posted_to_shipway = 1 AND docstatus = 0
		ORDER BY creation DESC """, as_list=1)
	for tracks in pending_ships:
		track_doc = frappe.get_doc("Carrier Tracking", tracks[0])
		track_doc.flags.ignore_permissions = True
		getOrderShipmentDetails(track_doc)
		frappe.db.commit()

def pushOrderData(track_doc):
	#First check if the AWB for the Same Shipper is there is Shipway if its there then
	if track_doc.get("__islocal") != 1 and track_doc.posted_to_shipway == 0:
		check_upload = check_order_upload(track_doc)
		username, license_key = get_shipway_pass()
		if check_upload.get("status") != "Success":
			url = get_shipway_url() + "pushOrderData"
			post_data = {
				"username": username,
				"password": license_key,
				"carrier_id": frappe.get_value("Transporters", track_doc.carrier_name,
					"shipway_id"),  #from transporters doc
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


def getOrderShipmentDetails(track_doc):
	print("Processing Carrier Tracking #: " + track_doc.name)
	if track_doc.get("__islocal") != 1 and track_doc.status != "Delivered":
		response = check_order_upload(track_doc)
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
			if web_response.get("awbno"):
				track_doc.awb_number = web_response.get("awbno")
			track_doc.recipient = web_response.get("recipient")
			if track_doc.status == "Delivered":
				track_doc.delivery_date_time = web_response.get("time")
			else:
				track_doc.delivery_date_time = None

			track_doc.save()
		else:
			track_doc.status = "Posting Error"
	elif track_doc.status == 'Delivered':
		frappe.msgprint(("{0} is Already Delivered").format(track_doc.name))
			
def check_order_upload(track_doc):
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