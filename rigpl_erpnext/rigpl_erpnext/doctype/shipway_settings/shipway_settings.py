# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import json
from frappe.model.document import Document
from frappe.integrations.utils import make_get_request, make_post_request, create_request_log
from rigpl_erpnext.rigpl_erpnext.scheduled_tasks.shipment_data_update import get_shipway_url

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
		25  = Closed#
		CRTA = Customer Refused
		CNA = Consignee Unavailable
		DEX = Delivery Exception
		DRE = Delivery Rescheduled
		PNR = COD Payment Not Ready
		LOST = Lost
	'''
	def get_carriers(self):
		url = get_shipway_url() + "carriers"
		carriers = requests.get(url=url, verify=False)
		json_response = json.loads(carriers.text)
		text = "Courier Name\t\t\t\tCourier ID\n"
		courier_list = json_response.get("couriers")
		for entry in courier_list:
			courier_name = entry.get("courier_name")
			courier_id = entry.get("id")
			text += str(courier_name) + "\t\t\t\t" + str(courier_id) + "\n"
		self.carrier_list = text
		self.save()