# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import sys
import json
from frappe.model.document import Document
from frappe.utils import get_url, call_hook_method, cint
from frappe.integrations.utils import make_get_request, make_post_request, create_request_log


class CarrierTracking(Document):
	def validate(self):
		if self.document == "Sales Invoice":
			si_doc = frappe.get_doc("Sales Invoice",self.document_name)
			if self.carrier_name == si_doc.transporters and self.awb_number == si_doc.lr_no:
				self.invoice_integrity = 1
			else:
				self.invoice_integrity = 0
		'''
		Check Carrier and LR No with Sales Invoice
		Order ID = ID of the Tracking Number (DONE)
		Don't allow if the document is NOT SAVE (DONE)
		Don't allow multiple AWB numbers to be posted to Shipway instead just pull the data 
		from Shipway (TOO COMPLEX since we cannot change shipment data via API)
		Validation check the Document Number with DOCTYPE and AWB number should not 
		repeat with Same Carrier (TOO COMPLEX since we cannot change shipment data via API)
		'''

	def pushOrderData(self):
		#First check if the AWB for the Same Shipper is there is Shipway if its there then
		if self.get("__islocal") != 1 and self.posted_to_shipway == 0:
			check_upload = self.check_order_upload()
			username, license_key = self.get_shipway_pass()
			if check_upload.get("status") != "Success":
				url = self.get_shipway_url() + "pushOrderData"
				post_data = {
					"username": username,
					"password": license_key,
					"carrier_id": frappe.get_value("Transporters", self.carrier_name,
						"shipway_id"),  #from transporters doc
					"awb": self.awb_number,
					"order_id": self.name,
					"first_name": "Rohit",
					"last_name": "Cutting Tools",
					"email": "gmail@gmail.com",
					"phone": "9999999999",
					"products": "N/A"
					}
				post_response = make_post_request(url=url, auth=None, headers=None, \
					data=json.dumps(post_data))
				if post_response.get("status") == "Success":
					self.status = "Shipment Data Uploaded"
					self.posted_to_shipway = 1
					self.save()
				else:
					self.status = "Posting Issues"
					frappe.throw("Some Issues")
			else:
				self.posted_to_shipway = 1
				self.save()
		elif self.posted_to_shipway == 1:
			frappe.msgprint("Already Posted to Shipway")


	def getOrderShipmentDetails(self):
		if self.get("__islocal") != 1 and self.status != "Delivered":
			response = self.check_order_upload()
			self.json_reply = str(response)

			if response.get("status") == "Success":
				self.scans = []
				web_response = response.get("response")
				web_scans = web_response.get("scan")

				if web_response.get("current_status_code") == "DEL":
					self.status = "Delivered"
				elif web_response.get("current_status_code") == "NFI":
					self.status = "No Information"
				else:
					self.status = "In Transit"
				if web_scans:
					for scan in web_scans:
						self.append("scans", scan)

				self.status_code = web_response.get("current_status_code")
				self.pickup_date = web_response.get("pickupdate")
				self.ship_to_city = web_response.get("to")
				if web_response.get("awbno"):
					self.awb_number = web_response.get("awbno")
				self.recipient = web_response.get("recipient")
				if self.status == "Delivered":
					self.delivery_date_time = web_response.get("time")
				else:
					self.delivery_date_time = None

				self.save()
			else:
				self.status = "Posting Error"
				
	def check_order_upload(self):
		username, license_key = self.get_shipway_pass()
		url = self.get_shipway_url() + "getOrderShipmentDetails"
		scans_list = []
		request = {
		    "username": username,
		    "password": license_key,
		    "order_id": self.name
		    }
		response = make_post_request(url=url, auth=None, headers=None, data=json.dumps(request))
		#frappe.msgprint(str(response))
		return response

	def get_shipway_url(self):
		return "https://shipway.in/api/"

	def get_shipway_pass(self):
		shipway_settings = frappe.get_doc("Shipway Settings")
		username = shipway_settings.username
		license_key = shipway_settings.license_key

		return username, license_key 