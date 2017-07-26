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