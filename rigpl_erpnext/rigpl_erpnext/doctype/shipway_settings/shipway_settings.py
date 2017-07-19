# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from frappe.integrations.utils import make_get_request, make_post_request, create_request_log

class ShipwaySettings(Document):
	'''
		Status Codes in Shipway
		current_status_code === Status Description
		DEL = Delivered
		INT = In Transit
		UND = Undelivered
		RTO = RTO
		RTD = RTO Delivered
		CAN = Cancelled
		SCH = Shipment Booked
		PKP = Picked Up
		ONH = On Hold
		OOD = Out for Delivery
		NWI = Network Issue
		DNB = Delivery Next Day
		NFI = Not Found/Incorrect
		ODA = Out of Delivery Area
		OTH = Others
		SMD = Delivery Delayed
		22  = Address Incorrect
		23  = Delivery Attempted
		24  = Pending- Undelivered
		25  = Closed
		CRTA = Customer Refused
		CNA = Consignee Unavailable
		DEX = Delivery Exception
		DRE = Delivery Rescheduled
		PNR = COD Payment Not Ready
		LOST = Lost
	'''
	def get_carriers(self):
		url = self.get_shipway_url() + "carriers"
		carriers = make_post_request(url=url, auth=None, headers=None, data=None)
		text = "Courier Name\t\t\t\tCourier ID\n"
		courier_list = carriers.get("couriers")
		for entry in courier_list:
			courier_name = entry.get("courier_name")
			courier_id = entry.get("id")
			text += str(courier_name) + "\t\t\t\t" + str(courier_id) + "\n"
		self.carrier_list = text
		self.save()

	@frappe.whitelist()
	def pushOrderData(self, track_doc):
		frappe.msgprint("Hello")
		#First check if the AWB for the Same Shipper is there is Shipway if its there then
		if track_doc.get("__islocal") != 1 and track_doc.posted_to_shipway == 0:
			check_upload = self.check_order_upload(track_doc)
			if check_upload.get("status") != "Success":
				url = self.get_shipway_url() + "pushOrderData"
				post_data = {
					"username": self.username,
					"password": self.license_key,
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
				post_response = make_post_request(url=url, auth=None, headers=None, \
					data=json.dumps(post_data))
				if post_response.get("status") == "Success":
					track_doc.status = "Shipment Data Uploaded"
					track_doc.posted_to_shipway = 1
					track_doc.save()
				else:
					track_doc.status = "Posting Issues"
					frappe.throw("Some Issues")
			else:
				track_doc.posted_to_shipway = 1
				track_doc.save()

	@frappe.whitelist()
	def getOrderShipmentDetails(self, track_doc):
		if track_doc.get("__islocal") != 1 and track_doc.status != "Delivered":
			response = self.check_order_upload(track_doc)
			track_doc.json_reply = str(response)

			if response.get("status") == "Success":
				track_doc.scans = []
				web_response = response.get("response")
				web_scans = web_response.get("scan")

				if web_response.get("current_status_code") == "DEL":
					track_doc.status = "Delivered"
				elif web_response.get("current_status_code") == "NFI":
					track_doc.status = "No Information"
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
				
	def check_order_upload(self, track_doc):
		url = self.get_shipway_url() + "getOrderShipmentDetails"
		scans_list = []
		request = {
		    "username": self.username,
		    "password": self.license_key,
		    "order_id": track_doc.name
		    }
		response = make_post_request(url=url, auth=None, headers=None, data=json.dumps(request))
		#frappe.msgprint(str(response))
		return response

	def get_shipway_url(self):
		return "https://shipway.in/api/"

	def send_bulk_tracks(self, track_doc):
		#Pause of 5seconds for sending data means 720 shipment data per hour can be sent
		#Get the list of all Shipments which are not posted
		pending_tracks = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` WHERE posted_to_shipway = 0 ORDER BY creation DESC """, as_list=1)
		for tracks in pending_tracks:
			track_doc = frappe.get_doc("Carrier Tracking", tracks[0])
			frappe.throw(str(tracks[0]))