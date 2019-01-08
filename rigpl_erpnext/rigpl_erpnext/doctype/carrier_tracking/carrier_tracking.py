# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, re
import json
from frappe.model.document import Document
from frappe.utils import get_url, call_hook_method, cint
from frappe.integrations.utils import make_get_request, make_post_request, create_request_log
from rigpl_erpnext.rigpl_erpnext.scheduled_tasks.shipment_data_update import *
from rigpl_erpnext.rigpl_erpnext.validations.sales_invoice import create_new_carrier_track
from frappe.utils import flt, cint, cstr
from frappe.utils.file_manager import save_file, remove_all
import fedex
import base64
import datetime
from fedex.tools.conversion import sobject_to_dict
from fedex.tools.conversion import sobject_to_json


class CarrierTracking(Document):
	uom_mapper = {"Kg":"KG", "LB":"LB", "kg": "KG", "cm": "CM"}
	allowed_docs = ['Sales Invoice', 'Purchase Order', 'Customer', 'Supplier', 'Company', 'Employee', 'Sales Partner']
	allowed_docs_items = ['Sales Invoice', 'Purchase Order']

	def validate(self):
		self.update_fields()
		trans_doc = frappe.get_doc("Transporters", self.carrier_name)
		from_address_doc = frappe.get_doc("Address", self.from_address)
		to_address_doc = frappe.get_doc("Address", self.to_address)
		self.gen_add_validations(trans_doc, from_address_doc, to_address_doc)

		if trans_doc.fedex_credentials == 1:
			self.fedex_account_number = trans_doc.fedex_account_number
			self.sales_invoice_validations_fedex()
			self.ctrac_validations()
			self.carrier_validations(trans_doc, from_address_doc, to_address_doc)
		else:
			self.non_fedex_validations()

	def update_fields(self):
		if self.document == 'Sales Invoice':
			si_doc = frappe.get_doc("Sales Invoice",self.document_name)
			self.receiver_document = "Customer"
			self.receiver_name = si_doc.customer
			tax_temp_doc = frappe.get_doc("Sales Taxes and Charges Template", \
				si_doc.taxes_and_charges)
			if not self.from_address and self.get("__islocal") == 1:
				if not tax_temp_doc.from_address:
					frappe.throw("Update From Address in Tax Template {}".format(tax_temp_doc.name))
				else:
					self.from_address = tax_temp_doc.from_address
			elif not self.from_address:
				frappe.throw("From Address is Needed before Saving the Document")
				
			self.to_address = si_doc.shipping_address_name
			self.contact_person = si_doc.contact_person
			self.carrier_name = si_doc.transporters
			if tax_temp_doc.is_sample == 1:
				self.purpose = 'SAMPLE'
				if self.amount == 0:
					self.amount = 1
			else:
				self.purpose = 'SOLD'
				self.amount = si_doc.grand_total
			self.currency = si_doc.currency
		elif self.document == 'Purchase Order':
			po_doc = frappe.get_doc("Purchase Order",self.document_name)
			self.receiver_document = "Supplier"
			self.receiver_name = po_doc.supplier
			tax_temp_doc = frappe.get_doc("Purchase Taxes and Charges Template", \
				po_doc.taxes_and_charges)
			
			if not self.from_address and self.get("__islocal") == 1:
				if not tax_temp_doc.from_address:
					frappe.throw("Update From Address in Tax Template {}".format(tax_temp_doc.name))
				else:
					self.from_address = tax_temp_doc.from_address
			elif not self.from_address:
				frappe.throw("From Address is Needed before Saving the Document")

			self.to_address = po_doc.supplier_address
			self.contact_person = po_doc.contact_person
			self.purpose = 'NOT_SOLD'
			self.amount = po_doc.grand_total
			self.currency = po_doc.currency
		elif self.document in ('Customer', 'Supplier', 'Company', 'Sales Partner', 'Employee'):
			if not self.carrier_name:
				frappe.throw('Select the Carrier Through which Shipment is to be Sent')
			if not self.purpose:
				frappe.throw('Select the Purpose of Shipment')
			if not self.from_address:
				frappe.throw('Select the Address from which Shipment is to be Sent')
			if not self.shipment_notes:
				frappe.throw('Add a Small description of the Type of Things in Consignment in Shipment Notes')
			cu_doc = frappe.get_doc(self.document, self.document_name)
			self.receiver_document = self.document
			self.receiver_name = self.document_name
			#Validate To Address and contact person of customer or supplier only
			if not self.to_address:
				def_to_add = frappe.db.sql("""SELECT ad.name 
					FROM `tabAddress` ad, `tabDynamic Link` dl 
					WHERE  dl.link_doctype = '%s' AND dl.link_name = '%s' 
					AND dl.parent = ad.name"""%(self.document, self.document_name), as_list=1)
				self.to_address = def_to_add[0][0]
			if not self.contact_person:
				def_contact = frappe.db.sql("""SELECT con.name 
					FROM `tabContact` con, `tabDynamic Link` dl 
					WHERE  dl.link_doctype = '%s' AND dl.link_name = '%s' 
					AND dl.parent = con.name"""%(self.document, self.document_name), as_list=1)
				self.contact_person = def_contact[0][0]
			if self.to_address or self.contact_person:
				linked_add = frappe.db.sql("""SELECT link_name FROM `tabDynamic Link` 
					WHERE parent = '%s' AND link_doctype = '%s' AND link_name = '%s'"""%(self.to_address, self.document, self.document_name))
				if not linked_add:
					frappe.throw("To Address: {} not from {}: {}".\
						format(self.to_address, self.document, self.document_name))

				linked_con = frappe.db.sql("""SELECT link_name FROM `tabDynamic Link` 
					WHERE parent = '%s' AND link_doctype = '%s' AND link_name = '%s'"""%(self.to_address, self.document, self.document_name))
				if not linked_con:
					frappe.throw("Contact: {} not from {}: {}".\
						format(self.contact_person, self.document, self.document_name))
			if not self.amount:
				self.amount = 1
			self.currency = 'INR'


	def non_fedex_validations(self):
		if self.document == 'Sales Invoice':
			si_doc = frappe.get_doc("Sales Invoice", self.document_name)
			if self.invoice_integrity != 1:
				if self.posted_to_shipway == 1:
					si_awb = re.sub('[^A-Za-z0-9]+', '', str(si_doc.lr_no))
					if re.sub('[^A-Za-z0-9]+', '', str(self.awb_number)) != si_awb or \
						si_doc.transporters != self.carrier_name:
						create_new_carrier_track(si_doc, frappe)
						self.docstatus = 1
				else:
					self.awb_number = si_doc.lr_no
					self.carrier_name = si_doc.transporters

	def gen_add_validations(self, trans_doc, from_address_doc, to_address_doc):
		if self.status == "Delivered":
			self.docstatus = 1

		if from_address_doc.pincode is None:
			frappe.throw(("No Pincode Defined for Address {} if pincode not known enter \
				NA").format(self.from_address))

		if self.document == 'Sales Invoice':
			si_doc = frappe.get_doc("Sales Invoice",self.document_name)
			if self.carrier_name == si_doc.transporters and self.awb_number == si_doc.lr_no:
				self.invoice_integrity = 1
			else:
				self.invoice_integrity = 0

	def carrier_validations(self, trans_doc, from_address_doc, to_address_doc):
		contact_doc = frappe.get_doc('Contact', self.contact_person)
		self.set_recipient_email(to_address_doc, contact_doc)
		if trans_doc.is_outward_only==1:
			if self.is_inward != 1:
				if from_address_doc.is_your_company_address != 1:
					frappe.throw(('Since {} is Outward Transporter, \
						From Address Should be Owned Address').format(self.carrier_name))
			else:
				if from_address_doc.is_your_company_address == 1:
					frappe.throw(('Since {} is Marked For Inward Shipment, \
						From Address Should Not be Owned Address').format(self.carrier_name))
		else:
			if from_address_doc.is_your_company_address == 1:
				frappe.throw(('Since {} is Inward Transporter, \
					From Address Should be not be Owned Address').format(self.carrier_name))

			if to_address_doc.is_your_company_address != 1:
				frappe.throw(('Since {} is Inward Transporter, \
					To Address Should be Owned Address').format(self.carrier_name))
		
		if trans_doc.is_export_only == 1:
			if from_address_doc.country == to_address_doc.country:
				frappe.throw(('Since {} is Export Transporter, \
					To Address Should be not be in {}').format(self.carrier_name, \
					from_address_doc.country))

		if trans_doc.is_imports_only == 1:
			if from_address_doc.is_your_company_address == 1:
				frappe.throw(('Since {} is Import Transporter, \
					From Address Should be not owned Address').format(self.carrier_name))

			if from_address_doc.country == to_address_doc.country:
				frappe.throw(('Since {} is Import Transporter, \
					From Address Country Should not be Same as To \
					Address').format(self.carrier_name))

			if from_address_doc.is_your_company_address != 1:
				frappe.throw(('Since {} is Import Transporter, \
					To Address Should be Owned Address').format(self.carrier_name))

		if trans_doc.is_domestic_only == 1:
			if from_address_doc.country != to_address_doc.country:
				frappe.throw(('Since {} is Domestic Transporter, \
					From and To Address Should be in Same Country').format(self.carrier_name))

		if flt(trans_doc.minimum_weight) > 0 and self.get("__islocal") != 1:
			if flt(trans_doc.minimum_weight) > flt(self.total_weight):
				frappe.throw(('Minimum Weight for {} is \
					{} kgs').format(self.carrier_name, trans_doc.minimum_weight))

		if trans_doc.maximum_amount > 0:
			if trans_doc.maximum_amount < self.amount:
				frappe.throw(('Maximum Value for {} is \
					{}').format(self.carrier_name, trans_doc.maximum_amount))

		if self.amount < 1:
			frappe.throw("Amount Should be One or More than One")

	def ctrac_validations(self):
		#Only allow SYSTEM MANAGER to make changes to the DOCUMENT with SENDER
		#DUTIES PAYMENT (Very RISKY OPTION hence this Validation)
		if self.duties_payment_by == 'SENDER':
			user = frappe.session.user
			roles = frappe.db.sql("""SELECT role FROM `tabHas Role` 
				WHERE parent = '%s' """ %user, as_list=1)
			if any("System Manager" in s  for s in roles):
				pass
			else:
				frappe.throw("Only System Managers are Allowed to Make Changes to {} as \
					Duties Payment is by {}".format(self.name, self.duties_payment_by))

		#Update Package Details and also Validate UOM and Volumetric Weight
		for pkg in self.shipment_package_details:
			pkg_doc = frappe.get_doc("Shipment Package", pkg.shipment_package)
			pkg.package_name = pkg_doc.title
			pkg.volumetric_weight = pkg_doc.volumetric_weight_in_kgs
			if pkg.weight_uom != 'Kg':
				frappe.throw("Only Kg is allowed currently in Package Weight UoM")
			if flt(pkg.volumetric_weight) > flt(pkg.package_weight):
				frappe.throw("Parcel Weight Less than Volumetric Weight, USE Smaller \
					Package or Change the Weight in Row {}".format(pkg.idx))

	def sales_invoice_validations_fedex(self):
		if self.document in CarrierTracking.allowed_docs_items:
			si_doc = frappe.get_doc(self.document, self.document_name)
			other_tracks = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` 
				WHERE document = '%s' AND document_name = '%s' AND docstatus != 2
				AND name != '%s'"""%(self.document, self.document_name, self.name), as_list=1)
			if other_tracks:
				frappe.throw('{}: {} is already linked to {}'.format(self.document, \
					self.document_name, other_tracks[0][0]))
			if self.awb_number:
				if self.awb_number != si_doc.lr_no:
					self.set_invoice_lr_no(self.document_name, self.document)
		else:
			if self.purpose == 'SOLD':
				frappe.throw('Purpose SOLD only possible for Sales Invoices')
		
		total_weight = 0
		for d in self.shipment_package_details:
			total_weight += d.package_weight
			self.weight_uom = d.weight_uom
			self.total_handling_units = d.idx
		if total_weight > 0:
			if flt(self.total_weight) != flt(total_weight):
				self.total_weight = total_weight

	def pushdata (self):
		pushOrderData (self)


	def getdata(self):
		getOrderShipmentDetails(self)

	def validate_address(self):
		credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
			transporter_doc, contact_doc = self.get_required_docs()
		self.address_validation(credentials, to_address_doc, to_country_doc)

	def available_services(self):
		credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
			transporter_doc, contact_doc = self.get_required_docs()
		self.availabiltiy_commitment(credentials, from_address_doc, to_address_doc, \
			from_country_doc, to_country_doc)

	def get_rates(self):
		credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
			transporter_doc, contact_doc = self.get_required_docs()
		self.rate_service(credentials, from_address_doc, to_address_doc, \
			from_country_doc, to_country_doc, transporter_doc)

	def book_shipment(self):
		if self.shipment_package_details:
			for packages in self.shipment_package_details:
				if packages.tracking_id and packages.idx == 1:
					frappe.throw(("Shipment Already Booked with Tracking Number: \
						{}").format(self.awb_number))
				else:
					if self.get("__islocal") != 1:
						if packages.idx == 1:
							credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
								transporter_doc, contact_doc = self.get_required_docs()
							self.rate_service(credentials, from_address_doc, to_address_doc, \
								from_country_doc, to_country_doc, transporter_doc)
							self.create_shipment_service(credentials, from_address_doc, to_address_doc, \
								from_country_doc, to_country_doc, transporter_doc, contact_doc)
					else:
						frappe.throw('Save the Transaction before Booking Shipment')
		else:
			frappe.throw("To Book Shipment, Package Details is Mandatory")

	def delete_shipment(self):
		credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
			transporter_doc, contact_doc = self.get_required_docs()
		self.delete_shipment_service(credentials, transporter_doc)
		frappe.db.set_value(self.doctype, self.name, "status", "Not Booked")
		if self.document == 'Sales Invoice':
			self.set_invoice_lr_no(self.document_name, self.document)


	def get_nearest_office(self):
		credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
			transporter_doc, contact_doc = self.get_required_docs()
		self.location_service(credentials, from_address_doc, from_country_doc)


	def create_shipment_service(self, credentials, from_address_doc, to_address_doc, \
		from_country_doc, to_country_doc, transporter_doc, contact_doc):
		from fedex.services.ship_service import FedexProcessShipmentRequest
		customer_transaction_id = self.name  # Optional transaction_id
		shipment = FedexProcessShipmentRequest(credentials, \
			customer_transaction_id=customer_transaction_id)
		self.set_shipment_details(shipment, credentials, transporter_doc)
		shipper_details =  self.set_shipper_info(shipment, from_address_doc, credentials)
		recipient_details = self.set_recipient_info(shipment, to_address_doc, credentials)
		self.set_fedex_label_info(shipment)
		self.set_commodities_info(self, shipment)
		self.set_commercial_invoice_info(shipment)
		self.set_email_notification(shipment, from_address_doc, to_address_doc, contact_doc)
		pkg_count = self.total_handling_units
		for index, pkg in enumerate(self.shipment_package_details):
			pkg_doc = frappe.get_doc("Shipment Package", pkg.shipment_package)
			if index:
					shipment.RequestedShipment.MasterTrackingId.TrackingNumber = self.awb_number
					shipment.RequestedShipment.MasterTrackingId.TrackingIdType.value = \
						transporter_doc.type_of_service
					self.set_package_data(pkg, pkg_doc, shipment, index + 1)
			else:
				shipment.RequestedShipment.TotalWeight.Units = self.uom_mapper.get(self.weight_uom)
				shipment.RequestedShipment.TotalWeight.Value = self.total_weight
				self.set_package_data(pkg, pkg_doc, shipment, index + 1)
				shipment.send_validation_request()
			shipment.send_request()
			self.validate_fedex_shipping_response(shipment, pkg.idx)
			tracking_id = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].TrackingIds[0].TrackingNumber
			if index == 0:
				self.awb_number = tracking_id
			self.status = "Booked"
			self.set_package_details(pkg, cstr(shipment.response), tracking_id)
			self.store_label(self, shipment, tracking_id, self.doctype, self.name)
			self.save()
		return shipment


	def delete_shipment_service(self, credentials, transporter_doc):
		from fedex.services.ship_service import FedexDeleteShipmentRequest
		tracking_id = self.awb_number
		del_request = FedexDeleteShipmentRequest(credentials)
		del_request.DeletionControlType = "DELETE_ALL_PACKAGES"
		del_request.TrackingId.TrackingNumber = tracking_id
		del_request.TrackingId.TrackingIdType = transporter_doc.type_of_service
		try:
			del_request.send_request()
		except Exception as ex:
			frappe.throw('Fedex API: ' + cstr(ex))

		if del_request.response.HighestSeverity == "SUCCESS":
			frappe.msgprint('Shipment with tracking number %s is deleted successfully.' % tracking_id)
			self.remove_tracking_details(del_request)
		else:
			self.remove_tracking_details(del_request)
			self.show_notification(del_request)
			frappe.msgprint('Canceling of Shipment in Fedex service failed.')

	def remove_tracking_details(self, del_request):
		frappe.db.set_value(self.doctype, self.name, "awb_number", "NA")
		for pkg in (self.shipment_package_details):
			if pkg.tracking_id:
				frappe.db.set_value("Shipment Package Details", pkg.name, "tracking_id", "")
		remove_all(self.doctype, self.name)

	def validate_fedex_shipping_response(self, shipment, package_id):
		msg = ''
		try:
			msg = shipment.response.Message
		except:
			pass
		if shipment.response.HighestSeverity == "SUCCESS":
			frappe.msgprint('Shipment is created successfully in Fedex service for package {0}.'.\
				format(package_id))
		elif shipment.response.HighestSeverity in ["NOTE", "WARNING"]:
			frappe.msgprint('Shipment is created in Fedex service for package {0} with the following \
				message:\n{1}'.format(package_id, msg))
			self.show_notification(shipment)
		else:  # ERROR, FAILURE
			self.show_notification(shipment)
			frappe.throw('Creating of Shipment in Fedex service for package {0} failed.'.format(package_id))


	def set_package_data(self, pkg, pkg_doc, shipment, pkg_no):
		package = self.set_package_weight(shipment, pkg)
		self.set_package_dimensions(shipment, pkg_doc, package)
		package.SequenceNumber = pkg_no
		shipment.RequestedShipment.RequestedPackageLineItems = [package]
		shipment.RequestedShipment.PackageCount = self.total_handling_units
		# shipment.add_package(package)

	def set_package_dimensions(self, shipment, pkg, package):
		# adding package dimensions
		dimn = shipment.create_wsdl_object_of_type('Dimensions')
		dimn.Length = pkg.length
		dimn.Width = pkg.width
		dimn.Height = pkg.height
		dimn.Units = self.uom_mapper.get(pkg.uom)
		package.Dimensions = dimn

	def rate_service(self, credentials, from_address_doc, to_address_doc, \
			from_country_doc, to_country_doc, transporter_doc):
		stop = 0
		from fedex.services.rate_service import FedexRateServiceRequest
		# Optional transaction_id
		customer_transaction_id = "*** RateService Request v18 using Python ***"  
		rate_request = FedexRateServiceRequest(credentials, \
			customer_transaction_id=customer_transaction_id)
		rate_request.ReturnTransitAndCommit = True
		rate_request.RequestedShipment.DropoffType = 'REGULAR_PICKUP'
		rate_request.RequestedShipment.ServiceType = transporter_doc.fedex_service_code
		rate_request.RequestedShipment.PackagingType = 'YOUR_PACKAGING'
		rate_request.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER'
		rate_request.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = \
		    credentials.account_number
		rate_request.RequestedShipment.CustomsClearanceDetail.DutiesPayment.PaymentType = self.duties_payment_by
		rate_request.RequestedShipment.CustomsClearanceDetail.CustomsValue.Amount = self.amount
		rate_request.RequestedShipment.CustomsClearanceDetail.CustomsValue.Currency = self.currency
		rate_request.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor.ResponsibleParty.AccountNumber = \
			credentials.account_number if self.duties_payment_by == "SENDER" else ""

		self.set_shipper_info(rate_request, from_address_doc, credentials)
		self.set_recipient_info(rate_request, to_address_doc, credentials)
		#self.set_commodities_info(self, rate_request)
		self.set_commercial_invoice_info(rate_request)

		for row in self.shipment_package_details:
			package1 = self.set_package_weight(rate_request, row)
			package1.GroupPackageCount = 1
			rate_request.add_package(package1)
		rate_request.send_request()
		# RateReplyDetails can contain rates for multiple ServiceTypes if ServiceType was set to None
		for service in rate_request.response.RateReplyDetails:
			for delivery in service:
				if delivery[0] == 'DeliveryTimestamp':
					self.expected_delivery_date = delivery[1]
			for detail in service.RatedShipmentDetails:
				for surcharge in detail.ShipmentRateDetail.Surcharges:
					if surcharge.SurchargeType == 'OUT_OF_DELIVERY_AREA':
						stop = 1
						frappe.msgprint("{}: ODA rate_request charge {}".\
							format(service.ServiceType, surcharge.Amount.Amount))

			for rate_detail in service.RatedShipmentDetails:
				self.shipment_cost = rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Amount
				self.shipment_cost_currency = rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Currency
				self.save()
		if stop == 1:
			frappe.throw('Out of Delivery Area, Booking of Shipment Not Allowed')

	def availabiltiy_commitment(self, credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc):
		from fedex.services.availability_commitment_service import FedexAvailabilityCommitmentRequest
		avc_request = FedexAvailabilityCommitmentRequest(credentials)
		avc_request.Origin.PostalCode = str(from_address_doc.pincode)[0:10]
		avc_request.Origin.CountryCode = from_country_doc.code
		avc_request.Destination.PostalCode = str(to_address_doc.pincode)[0:10]
		avc_request.Destination.CountryCode = to_country_doc.code
		avc_request.ShipDate = datetime.date.today().isoformat()
		avc_request.send_request()
		for option in avc_request.response.Options:
			frappe.msgprint("Ship Option:")
			if hasattr(option, 'Service'):
				frappe.msgprint("Service {}".format(option.Service))
			if hasattr(option, 'DeliveryDate'):
				frappe.msgprint("DeliveryDate {}".format(option.DeliveryDate))
			if hasattr(option, 'DeliveryDay'):
				frappe.msgprint("DeliveryDay {}".format(option.DeliveryDay))
			#if hasattr(option, 'DestinationStationId'):
			#	frappe.msgprint("DestinationStationId {}".format(option.DestinationStationId))
			#if hasattr(option, 'DestinationAirportId'):
			#	frappe.msgprint("DestinationAirportId {}".format(option.DestinationAirportId))
			if hasattr(option, 'TransitTime'):
				frappe.msgprint("TransitTime {}".format(option.TransitTime))
			frappe.msgprint("")
		#frappe.msgprint(str(avc_request.response))

	def address_validation(self, credentials, add_doc, country_doc):
		from fedex.services.address_validation_service import FedexAddressValidationRequest
		avs_request = FedexAddressValidationRequest(credentials)
		if add_doc.state_rigpl is not None and add_doc.state_rigpl != "":
			state_doc = frappe.get_doc("State", add_doc.state_rigpl)
		else:
			state_doc = ""
		if state_doc != "":
			state_code = state_doc.state_code
		else:
			state_code = ""
		address1 = avs_request.create_wsdl_object_of_type('AddressToValidate')
		address1.Address.StreetLines = [str(add_doc.address_line1)[0:35], \
			str(add_doc.address_line2)[0:35]]
		address1.Address.City = str(add_doc.city)[0:20]
		address1.Address.StateOrProvinceCode = str(state_code)[0:2]
		address1.Address.PostalCode = str(add_doc.pincode)[0:10]
		address1.Address.CountryCode = str(country_doc.code)[0:2]
		address1.Address.CountryName = add_doc.country
		address1.Address.Residential = add_doc.is_residential
		avs_request.add_address(address1)
		avs_request.send_request()
		
		for i in range(len(avs_request.response.AddressResults)):
			frappe.msgprint("Details for Address {}".format(i + 1))
			frappe.msgprint("The validated street is: {}"
				"".format(avs_request.response.AddressResults[i].EffectiveAddress.StreetLines))
			frappe.msgprint("The validated city is: {}"
				"".format(avs_request.response.AddressResults[i].EffectiveAddress.City))
			frappe.msgprint("The validated state code is: {}"
				"".format(avs_request.response.AddressResults[i].EffectiveAddress.StateOrProvinceCode))
			frappe.msgprint("The validated postal code is: {}"
				"".format(avs_request.response.AddressResults[i].EffectiveAddress.PostalCode))
			frappe.msgprint("The validated country code is: {}"
				"".format(avs_request.response.AddressResults[i].EffectiveAddress.CountryCode))

	def get_required_docs(self):
		transporter_doc = frappe.get_doc("Transporters", self.carrier_name)
		if transporter_doc.fedex_credentials != 1:
			frappe.throw(("{0} is not a Valid Fedex Account").format(self.carrier_name))
		to_address_doc = frappe.get_doc("Address", self.to_address)
		to_country_doc = frappe.get_doc("Country", to_address_doc.country)
		contact_doc = frappe.get_doc("Contact", self.contact_person)
		from_address_doc = frappe.get_doc("Address", self.from_address)
		from_country_doc = frappe.get_doc("Country", from_address_doc.country)
		credentials = self.get_fedex_credentials(transporter_doc)
		return credentials, from_address_doc, to_address_doc, from_country_doc, \
			to_country_doc,transporter_doc, contact_doc

	def set_shipment_details(self, call_type, credentials, transporter_doc):
		call_type.RequestedShipment.DropoffType = 'REGULAR_PICKUP' #self.drop_off_type
		call_type.RequestedShipment.ServiceType = transporter_doc.fedex_service_code
		call_type.RequestedShipment.PackagingType = 'YOUR_PACKAGING' #self.packaging_type
		call_type.RequestedShipment.ShippingChargesPayment.PaymentType = 'THIRD_PARTY' #self.shipping_payment_by
		call_type.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = \
		    credentials.account_number 
			#self.config_obj.account_number if self.shipping_payment_by == "SENDER" else self.shipping_payment_account

		call_type.RequestedShipment.CustomsClearanceDetail.DutiesPayment.PaymentType = self.duties_payment_by
		call_type.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor.ResponsibleParty.AccountNumber = \
			credentials.account_number if self.duties_payment_by == "SENDER" else ""
		return call_type	


	def set_shipper_info(self, call_type, ship_add_doc, credentials):
		from_country_doc = frappe.get_doc("Country", ship_add_doc.country)
		tin_no = ship_add_doc.gstin
		if (ship_add_doc.state_rigpl is not None  and ship_add_doc.state_rigpl != "") \
			and (ship_add_doc.country == 'India' or ship_add_doc.country == 'United States'):
			state_doc = frappe.get_doc("State", ship_add_doc.state_rigpl)
		else:
			state_doc = ""
		if state_doc != "":
			state_code = state_doc.state_code
		else:
			state_code = ""
		call_type.RequestedShipment.Shipper.AccountNumber = credentials.account_number
		call_type.RequestedShipment.Shipper.Contact.PersonName = str(ship_add_doc.address_title)[0:35]
		call_type.RequestedShipment.Shipper.Contact.CompanyName = str(ship_add_doc.address_title)[0:35]
		call_type.RequestedShipment.Shipper.Contact.PhoneNumber = str(ship_add_doc.phone)[0:15]
		call_type.RequestedShipment.Shipper.Address.StreetLines = [str(ship_add_doc.address_line1)[0:35],\
			 str(ship_add_doc.address_line2)[0:35]]
		call_type.RequestedShipment.Shipper.Address.City = str(ship_add_doc.city)[0:20]
		call_type.RequestedShipment.Shipper.Address.StateOrProvinceCode = state_code
		call_type.RequestedShipment.Shipper.Address.PostalCode = str(ship_add_doc.pincode)[0:10]
		call_type.RequestedShipment.Shipper.Address.CountryCode = from_country_doc.code
		call_type.RequestedShipment.Shipper.Address.Residential = ship_add_doc.is_residential
		if tin_no != 'NA' and tin_no is not None:
			tin_details = call_type.create_wsdl_object_of_type('TaxpayerIdentification')
			tin_details.TinType.value = "BUSINESS_NATIONAL"
			tin_details.Number = tin_no
			call_type.RequestedShipment.Shipper.Tins = [tin_details]

	def set_recipient_info(self, call_type, ship_add_doc, credentials):
		to_country_doc = frappe.get_doc("Country", ship_add_doc.country)
		contact_doc = frappe.get_doc("Contact", self.contact_person)
		if contact_doc.salutation:
			sal = contact_doc.salutation + " "
		else:
			sal = ""
		if contact_doc.first_name:
			first_n = contact_doc.first_name + " "
		else:
			first_n = ""
		if contact_doc.last_name:
			last_n = contact_doc.last_name
		else:
			last_n = ""
		full_name = sal + first_n + last_n
		
		tin_no = ship_add_doc.gstin
		if ship_add_doc.state_rigpl is not None and ship_add_doc.state_rigpl != "":
			state_doc = frappe.get_doc("State", ship_add_doc.state_rigpl)
		else:
			state_doc = ""
		if state_doc != "":
			state_code = state_doc.state_code
		else:
			state_code = ""

		#frappe.msgprint(str(state_code))

		call_type.RequestedShipment.Recipient.Contact.PersonName = \
			full_name[0:35]
		call_type.RequestedShipment.Recipient.Contact.CompanyName = \
			str(ship_add_doc.address_title)[0:35]
		call_type.RequestedShipment.Recipient.Contact.PhoneNumber = \
			(str(contact_doc.phone) + str(contact_doc.mobile_no))[0:15]
		call_type.RequestedShipment.Recipient.Address.StreetLines = \
			[str(ship_add_doc.address_line1)[0:35], str(ship_add_doc.address_line2)[0:35]]
		call_type.RequestedShipment.Recipient.Address.City = str(ship_add_doc.city)[0:20]
		call_type.RequestedShipment.Recipient.Address.StateOrProvinceCode = state_code
		call_type.RequestedShipment.Recipient.Address.PostalCode = str(ship_add_doc.pincode)[0:10]
		call_type.RequestedShipment.Recipient.Address.CountryCode = to_country_doc.code
		call_type.RequestedShipment.Recipient.Address.Residential = ship_add_doc.is_residential
		call_type.RequestedShipment.EdtRequestType = 'NONE' #Can be ALL or NONE
		call_type.RequestedShipment.FreightShipmentDetail.TotalHandlingUnits = \
			self.total_handling_units
		if tin_no != 'NA' and tin_no is not None:
			tin_details = call_type.create_wsdl_object_of_type('TaxpayerIdentification')
			tin_details.TinType.value = "BUSINESS_NATIONAL"
			tin_details.Number = tin_no
			call_type.RequestedShipment.Recipient.Tins = [tin_details]

		self.recipient_details = "\n".join([str(ship_add_doc.address_title)[0:35], full_name, \
					str(ship_add_doc.phone)[0:15], str(ship_add_doc.address_line1)[0:35], \
					str(ship_add_doc.address_line2)[0:35], str(ship_add_doc.city)[0:20] + " " + \
					str(state_code) + " " + str(ship_add_doc.pincode)[0:10] +  \
					" " + to_country_doc.code] )


	def set_commercial_invoice_info(self, call_type):
		call_type.RequestedShipment.CustomsClearanceDetail.CommercialInvoice.Purpose = self.purpose
		if call_type == 'shipment':
			call_type.RequestedShipment.CustomsClearanceDetail.CommercialInvoice.CustomsInvoiceNumber = \
				self.document_name if self.purpose == 'SOLD' else 'NA'

		call_type.RequestedShipment.ShippingDocumentSpecification.ShippingDocumentTypes = \
			"COMMERCIAL_INVOICE" if self.purpose == 'SOLD' else 'LABEL'

		call_type.RequestedShipment.ShippingDocumentSpecification.CommercialInvoiceDetail.Format.ImageType = "PDF"
		call_type.RequestedShipment.ShippingDocumentSpecification.CommercialInvoiceDetail.Format.StockType = "PAPER_LETTER"
		call_type.RequestedShipment.CustomsClearanceDetail.CustomsValue.Amount = self.amount
		call_type.RequestedShipment.CustomsClearanceDetail.CustomsValue.Currency = self.currency

	def set_package_weight(self, shipment, pkg):
		package = shipment.create_wsdl_object_of_type('RequestedPackageLineItem')
		package.PhysicalPackaging = 'BOX'
		# adding package weight
		package_weight = shipment.create_wsdl_object_of_type('Weight')
		package_weight.Units = self.uom_mapper.get(pkg.weight_uom)
		package_weight.Value = pkg.package_weight
		package.Weight = package_weight
		
		# Adding references as required by label evaluation process
		if self.purpose == 'SOLD':
			po_no = frappe.get_value(self.document, self.document_name, "po_no")
			si_no = self.document_name
			for ref, field in {"P_O_NUMBER":po_no, "INVOICE_NUMBER":si_no}.items():
				ref_data = shipment.create_wsdl_object_of_type('CustomerReference')
				ref_data.CustomerReferenceType = ref
				ref_data.Value = field
				package.CustomerReferences.append(ref_data)
		
		return package

	@staticmethod
	def store_label(self, shipment, tracking_id, ps_doctype, ps_name):
		label_data = base64.b64decode(shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].Label.Parts[0].Image)
		self.store_file('FEDEX-ID-{0}.pdf'.format(tracking_id), label_data, ps_doctype, ps_name)
		if hasattr(shipment.response.CompletedShipmentDetail, 'ShipmentDocuments'):
			inovice_data = base64.b64decode(shipment.response.CompletedShipmentDetail.ShipmentDocuments[0].Parts[0].Image)
			self.store_file('COMMER-INV-{0}-{1}.pdf'.format(ps_name, tracking_id), inovice_data, ps_doctype, ps_name)

	@staticmethod
	def store_file(file_name, image_data, ps_doctype, ps_name):
		frappe.msgprint(str(file_name))
		save_file(file_name, image_data, ps_doctype, ps_name, is_private=1)

	@staticmethod
	def set_fedex_label_info(shipment):
		shipment.RequestedShipment.LabelSpecification.LabelFormatType = "COMMON2D"
		shipment.RequestedShipment.LabelSpecification.ImageType = 'PDF'
		shipment.RequestedShipment.LabelSpecification.LabelStockType = 'PAPER_8.5X11_TOP_HALF_LABEL'
		shipment.RequestedShipment.LabelSpecification.LabelPrintingOrientation = 'BOTTOM_EDGE_OF_TEXT_FIRST'
		shipment.RequestedShipment.EdtRequestType = 'NONE'

		if hasattr(shipment.RequestedShipment.LabelSpecification, 'LabelOrder'):
		    del shipment.RequestedShipment.LabelSpecification.LabelOrder  # Delete, not using.

	@staticmethod
	def set_commodities_info(self, shipment):
		if self.document in CarrierTracking.allowed_docs_items:
			doc = frappe.get_doc(self.document, self.document_name)
			total_qty = 0
			for row in doc.items:
				total_qty += row.get("qty")
				hsn_doc = frappe.get_doc("GST HSN Code", frappe.get_value('Item', row.get('item_code'), 'customs_tariff_number'))
				item_doc = frappe.get_doc("Item", row.get("item_code"))
				country_doc = frappe.get_doc("Country", item_doc.country_of_origin)
				country_code = country_doc.code
			commodity_dict = {
				#"Name":row.get("item_code"),
				"Description": hsn_doc.description[0:30],
				"Weight": {"Units": self.uom_mapper.get(self.weight_uom),\
								 "Value":self.total_weight},
				"NumberOfPieces":int(self.total_handling_units),
				"HarmonizedCode": hsn_doc.name[0:8],
				"CountryOfManufacture":country_code,
				"Quantity":int(total_qty),
				"QuantityUnits":"EA",
				"UnitPrice":{"Currency":doc.currency, \
					"Amount":(doc.grand_total/total_qty) if self.purpose == 'SOLD' \
					else (1/total_qty)},
				"CustomsValue":{"Currency":doc.currency, "Amount":doc.grand_total \
					if self.purpose == 'SOLD' else 1}
			}
			shipment.RequestedShipment.CustomsClearanceDetail.Commodities.append(commodity_dict)
		elif self.document in CarrierTracking.allowed_docs:
			total_qty = self.total_handling_units
			desc = "OTHER PRINTED MATTER, INCLUDING PRINTED PICTURES AND PHOTOGRAPHS TRADE \
				ADVERTISING MATERIAL, COMMERCIAL CATALOGUES AND THE LIKE : POSTERS, PRINTED"
			country_doc = frappe.get_doc("Country", frappe.get_value("Address", self.from_address, "country"))
			country_code = country_doc.code
			commodity_dict = {
				#"Name":row.get("item_code"),
				"Description": desc[0:30],
				"Weight": {"Units": self.uom_mapper.get(self.weight_uom), "Value":self.total_weight},
				"NumberOfPieces":int(self.total_handling_units),
				"HarmonizedCode": '49111010',
				"CountryOfManufacture":country_code,
				"Quantity":int(total_qty),
				"QuantityUnits":"EA",
				"UnitPrice":{"Currency":self.currency, "Amount":(self.amount/total_qty)},
				"CustomsValue":{"Currency":self.currency, "Amount":self.amount}
			}
			shipment.RequestedShipment.CustomsClearanceDetail.Commodities.append(commodity_dict)
			total_value = self.amount
		else:
			frappe.throw("Currently only Booking Shipment is Available vide {}".format(CarrierTracking.allowed_docs))
			total_value = self.amount

	def set_recipient_email(self, to_address_doc, contact_doc):
		if not self.carrier_tracking_notifications:
			email_list = []
			if to_address_doc.email_id:
				email_list.append({"notify_to": "Recipient", "email_id": to_address_doc.email_id, "select_all": 1})
			if contact_doc.email_id:
				email_list.append({"notify_to": "Other-1", "email_id": contact_doc.email_id, "select_all": 1})
			if email_list:
				for e in email_list:
					row = self.append('carrier_tracking_notifications', {})
					row.update(e)
		if self.carrier_tracking_notifications:
			for row in self.carrier_tracking_notifications:
				if row.select_all == 1:
					row.shipment = 1
					row.delivery = 1
					row.tendered = 1
					row.exception = 1
				else:
					check = 0
					if row.shipment == 1:
						check += 1
					if row.delivery == 1:
						check += 1
					if row.tendered == 1:
						check += 1
					if row.exception == 1:
						check += 1
					if check > 0:
						pass
					else:
						frappe.throw('Atleast one of the Option is to be Selected for Row # {} in Notification Email Table'.format(row.idx))

	def set_email_notification(self, shipment, shipper_details, recipient_details, contact_doc):
		self.set_recipient_email(recipient_details, contact_doc)
		shipment.RequestedShipment.SpecialServicesRequested.EMailNotificationDetail.AggregationType = "PER_SHIPMENT"
		notify_mapper = {"Sender":"SHIPPER", "Recipient":"RECIPIENT", "Other-1":"OTHER", \
							"Other-2":"OTHER", "Other-3":"OTHER"}
		email_id_mapper = {"Sender":shipper_details, "Recipient":recipient_details, "Other-1":{}, \
							"Other-2":{}, "Other-3":{} }
		for row in self.carrier_tracking_notifications:
			notify_dict = {
				"EMailNotificationRecipientType":notify_mapper.get(row.notify_to, "SHIPPER"),
				"EMailAddress":email_id_mapper.get(row.notify_to, {}).get("email_id", \
					row.email_id or ""),
				"NotificationEventsRequested":[ fedex_event for event, fedex_event in \
					{"shipment":"ON_SHIPMENT", "delivery":"ON_DELIVERY", \
					"tendered":"ON_TENDER", "exception":"ON_EXCEPTION"}.items() if row.get(event)],
				"Format":"HTML",
				"Localization":{"LanguageCode":"EN", \
								"LocaleCode":email_id_mapper.get(row.notify_to, {}).get("country_code", "IN")}
			}
			shipment.RequestedShipment.SpecialServicesRequested.EMailNotificationDetail.Recipients.append(notify_dict)
	
	def location_service(self, credentials, from_address_doc, from_country_doc):
		from fedex.services.location_service import FedexSearchLocationRequest
		customer_transaction_id = "*** LocationService Request v3 using Python ***"  
		# Optional transaction_id
		location_request = FedexSearchLocationRequest(credentials, \
			customer_transaction_id=customer_transaction_id)
		location_request.Constraints.RadiusDistance.Value = self.radius
		location_request.Constraints.RadiusDistance.Units = self.radius_uom
		location_request.Address.PostalCode = from_address_doc.pincode[0:10]
		location_request.Address.CountryCode = from_country_doc.code
		location_request.send_request()
		response_dict = sobject_to_dict(location_request.response)
		frappe.msgprint(str(response_dict))

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

	def set_invoice_lr_no(self, si_name, si_doc):
		if self.awb_number:
			frappe.db.set_value(si_doc, si_name, "lr_no", self.awb_number)
		else:
			frappe.db.set_value(si_doc, si_name, "lr_no", "NA")

	def set_package_details(self, pkg, shipment_response, tracking_id):
		pkg.shipment_response = shipment_response
		pkg.tracking_id = tracking_id

	@staticmethod
	def get_company_data(request_data, field_name):
		shipper_details = frappe.db.get_value("Address", request_data.get("shipper_id"), "*", as_dict=True)
		field_value = frappe.db.get_value("Company", shipper_details.get("company"), field_name)
		return shipper_details, field_value