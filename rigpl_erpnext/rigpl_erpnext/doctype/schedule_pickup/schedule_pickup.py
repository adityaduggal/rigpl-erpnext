# -*- coding: utf-8 -*-
# Copyright (c) 2018, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import get_datetime
import json
import fedex
import datetime
from frappe.model.document import Document
from fedex.tools.conversion import sobject_to_dict
from fedex.tools.conversion import sobject_to_json

class SchedulePickup(Document):
	def schedule_pickup(self):
		credentials, from_address_doc, from_country_doc, \
			transporter_doc = self.get_required_docs()
		#request_data = json.loads(request_data)
		self.schedule_pickup_service(credentials,from_address_doc, from_country_doc, \
			transporter_doc)


	def schedule_pickup_service (self, credentials, from_address_doc, \
		from_country_doc, transporter_doc):
		from_state_doc = frappe.get_doc("State", from_address_doc.state_rigpl)
		from fedex.services.pickup_service import FedexCreatePickupRequest
		customer_transaction_id = self.name  # Optional transaction_id
		pickup_service = FedexCreatePickupRequest(credentials)
		pickup_service.OriginDetail.PickupLocation.Contact.PersonName = \
			from_address_doc.address_title[0:35]
		pickup_service.OriginDetail.PickupLocation.Contact.EMailAddress = from_address_doc.email_id
		pickup_service.OriginDetail.PickupLocation.Contact.CompanyName = from_address_doc.address_title[0:35]
		pickup_service.OriginDetail.PickupLocation.Contact.PhoneNumber = from_address_doc.phone[0:15]
		pickup_service.OriginDetail.PickupLocation.Address.StateOrProvinceCode = from_state_doc.state_code
		pickup_service.OriginDetail.PickupLocation.Address.PostalCode = from_address_doc.pincode[0:10]
		pickup_service.OriginDetail.PickupLocation.Address.CountryCode = from_country_doc.code
		pickup_service.OriginDetail.PickupLocation.Address.StreetLines = [from_address_doc.address_line1[0:35],\
																	 from_address_doc.address_line2[0:35]]
		pickup_service.OriginDetail.PickupLocation.Address.City = from_address_doc.city[0:20]
		pickup_service.OriginDetail.PickupLocation.Address.Residential = True if from_address_doc.is_residential \
																			else False
		pickup_service.OriginDetail.PackageLocation = 'NONE'
		pickup_service.OriginDetail.ReadyTimestamp = get_datetime(self.ready_time).replace(microsecond=0).isoformat()
		pickup_service.OriginDetail.CompanyCloseTime = self.last_time if self.last_time else '20:00:00'
		pickup_service.CarrierCode = 'FDXE'
		pickup_service.PackageCount = self.no_of_packages

		package_weight = pickup_service.create_wsdl_object_of_type('Weight')
		package_weight.Units = 'KG'
		package_weight.Value = '1'
		pickup_service.TotalWeight = package_weight

		# DOMESTIC or INTERNATIONAL
		if transporter_doc.is_export_only == 1 or transporter_doc.is_imports_only == 1:
			dom_type = 'INTERNATIONAL'
		elif transporter_doc.is_domestic_only == 1:
			dom_type = 'DOMESTIC'
		else:
			frappe.throw("Error Transporter should be either DOMESTIC or INTERNATIONAL")
		pickup_service.CountryRelationship = dom_type

		#frappe.msgprint(str(sobject_to_json(pickup_service)))
		pickup_service.send_request()
		if pickup_service.response.HighestSeverity not in ["SUCCESS", "NOTE", "WARNING"]:
			self.show_notification(pickup_service)
			#frappe.throw(_('Pickup service scheduling failed.'))
			frappe.msgprint(str(pickup_service.response.HighestSeverity))
			frappe.msgprint(str(pickup_service.response.PickupConfirmationNumber))
			frappe.msgprint(str(pickup_service.response.Location))
		return { "response": pickup_service.response.HighestSeverity,
				  "pickup_id": pickup_service.response.PickupConfirmationNumber,
				  "location_no": pickup_service.response.Location
				}
	
	def get_required_docs(self):
		transporter_doc = frappe.get_doc("Transporters", self.carrier_name)
		if transporter_doc.fedex_credentials != 1:
			frappe.throw(("{0} is not a Valid Fedex Account").format(self.carrier_name))
		#to_address_doc = frappe.get_doc("Address", self.to_address)
		#to_country_doc = frappe.get_doc("Country", to_address_doc.country)
		#contact_doc = frappe.get_doc("Contact", self.contact_person)
		from_address_doc = frappe.get_doc("Address", self.pickup_address)
		from_country_doc = frappe.get_doc("Country", from_address_doc.country)
		credentials = self.get_fedex_credentials(transporter_doc)
		return credentials, from_address_doc, from_country_doc, transporter_doc

	def get_fedex_credentials(self, transporter_doc):
		from fedex.config import FedexConfig
		credentials = FedexConfig(key = transporter_doc.fedex_key,
				password = transporter_doc.fedex_password,
				account_number = transporter_doc.fedex_account_number,
				meter_number = transporter_doc.fedex_meter_number,
				use_test_server = transporter_doc.is_test_server)
		return credentials

	def show_notification(self, shipment):
		for notification in shipment.response.Notifications:
			frappe.msgprint('Code: %s, %s' % (notification.Code, notification.Message))