# -*- coding: utf-8 -*-
# Copyright (c) 2018, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.file_manager import save_file, remove_all
from frappe.utils import flt, cint, cstr
import fedex
import base64
import datetime
from frappe.model.document import Document
from fedex.tools.conversion import sobject_to_dict
from fedex.tools.conversion import sobject_to_json

class BookShipment(Document):
	uom_mapper = {"Kg":"KG", "LB":"LB", "kg": "KG", "cm": "CM"}

	def validate(self):
		if self.tracking_number:
			#self.docstatus = 1
			if self.reference_doctype == "Sales Invoice":
				#Check if same SI is not booked earlier Shipment
				bk_shipments = frappe.db.sql("""SELECT name, reference_docname 
					FROM `tabBook Shipment` 
					WHERE docstatus !=2 AND name <> '%s'"""%(self.name), as_list=1)
				for ship in bk_shipments:
					if ship[1] == self.reference_docname:
						frappe.throw("{} Shipment already booked for SI # {}".\
							format(ship[0], self.reference_docname))
				sid = frappe.get_doc(self.reference_doctype, self.reference_docname)
				if sid.docstatus != 0:
					frappe.throw("Shipment for Draft Invoices can only be Booked")
				else:
					sid.transporters = self.shipment_forwarder
					sid.lr_no = self.tracking_number
					sid.save()
		total_weight = 0
		for d in self.shipment_package_details:
			total_weight += d.package_weight
			self.weight_uom = d.weight_uom
			self.total_handling_units = d.idx
		if int(self.total_weight) != int(total_weight):
			self.total_weight = total_weight
		if self.reference_doctype == "Sales Invoice":
			self.purpose = 'SOLD'
			self.amount = frappe.get_value('Sales Invoice', self.reference_docname, "grand_total")
			self.currency = frappe.get_value('Sales Invoice', self.reference_docname, "currency")
		else:
			if self.purpose == 'SOLD':
				frappe.throw('Purpose SOLD only possible for Sales Invoices')

	def on_submit(self):
		if self.tracking_number:
			pass
		else:
			frappe.throw("Only Booked Shipments are Allowed to be Submitted")

	def on_cancel(self):
		self.delete_shipment()

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
		if self.tracking_number:
			frappe.msgprint(("Shipment already booked with Tracking No {0}".format(self.tracking_number)))
		else:
			if self.get("__islocal") != 1:
				credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
					transporter_doc, contact_doc = self.get_required_docs()
				self.rate_service(credentials, from_address_doc, to_address_doc, \
					from_country_doc, to_country_doc, transporter_doc)
				self.create_shipment_service(credentials, from_address_doc, to_address_doc, \
					from_country_doc, to_country_doc, transporter_doc, contact_doc)
			else:
				frappe.throw('Save the Transaction before Booking Shipment')

	def delete_shipment(self):
		credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
			transporter_doc, contact_doc = self.get_required_docs()
		self.delete_shipment_service(credentials, transporter_doc)

	def get_nearest_office(self):
		credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
			transporter_doc, contact_doc = self.get_required_docs()
		self.location_service(credentials, from_address_doc, from_country_doc)


	def create_shipment_service(self, credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
			transporter_doc, contact_doc):
		from fedex.services.ship_service import FedexProcessShipmentRequest
		customer_transaction_id = self.name  # Optional transaction_id
		shipment = FedexProcessShipmentRequest(credentials, customer_transaction_id=customer_transaction_id)
		self.set_shipment_details(shipment, credentials, transporter_doc)
		shipper_details =  self.set_shipper_info(shipment, from_address_doc, credentials)
		recipient_details = self.set_recipient_info(shipment, to_address_doc, credentials)
		self.set_fedex_label_info(shipment)
		self.set_commodities_info(self, shipment)
		self.set_commercial_invoice_info(shipment)
		#self.set_email_notification(shipment, doc, shipper_details, recipient_details)
		pkg_count = self.total_handling_units
		for index, pkg in enumerate(self.shipment_package_details):
			pkg_doc = frappe.get_doc("Shipment Package", pkg.shipment_package)
			if index:
					shipment.RequestedShipment.MasterTrackingId.TrackingNumber = self.tracking_number
					shipment.RequestedShipment.MasterTrackingId.TrackingIdType.value = transporter_doc.type_of_service
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
				self.tracking_number = tracking_id
			self.set_package_details(pkg, cstr(shipment.response), tracking_id)
			self.store_label(self, shipment, tracking_id, self.doctype, self.name)
			self.save()
		return shipment


	def delete_shipment_service(self, credentials, transporter_doc):
		from fedex.services.ship_service import FedexDeleteShipmentRequest
		tracking_id = self.tracking_number
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
			#frappe.get_doc(self.doctype, self.name)
		else:
			self.remove_tracking_details(del_request)
			self.show_notification(del_request)
			frappe.msgprint('Canceling of Shipment in Fedex service failed.')

	def remove_tracking_details(self, del_request):
		frappe.db.set_value(self.doctype, self.name, "tracking_number", "")
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
		rate_request.RequestedShipment.CustomsClearanceDetail.DutiesPayment.PaymentType = 'RECIPIENT'
		rate_request.RequestedShipment.CustomsClearanceDetail.CustomsValue.Amount = self.amount
		rate_request.RequestedShipment.CustomsClearanceDetail.CustomsValue.Currency = self.currency
		#rate_request.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor.ResponsibleParty.AccountNumber = \
		#	self.config_obj.account_number if doc.duties_payment_by == "SENDER" else doc.duties_payment_account

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
		    for detail in service.RatedShipmentDetails:
		        for surcharge in detail.ShipmentRateDetail.Surcharges:
		            if surcharge.SurchargeType == 'OUT_OF_DELIVERY_AREA':
		                frappe.msgprint("{}: ODA rate_request charge {}".\
		                	format(service.ServiceType, surcharge.Amount.Amount))

		    for rate_detail in service.RatedShipmentDetails:
		        #frappe.msgprint("{}: Net FedEx Charge {} {}".format(service.ServiceType, \
		        #	rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Currency, \
		        #	rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Amount))
		        self.shipment_cost = rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Amount
		        self.shipment_cost_currency = rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Currency
		        self.save()

	def availabiltiy_commitment(self, credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc):
		from fedex.services.availability_commitment_service import FedexAvailabilityCommitmentRequest
		avc_request = FedexAvailabilityCommitmentRequest(credentials)
		avc_request.Origin.PostalCode = from_address_doc.pincode
		avc_request.Origin.CountryCode = from_country_doc.code
		avc_request.Destination.PostalCode = to_address_doc.pincode
		avc_request.Destination.CountryCode = to_country_doc.code
		avc_request.ShipDate = datetime.date.today().isoformat()
		avc_request.send_request()
		response_dict = sobject_to_dict(avc_request.response)
		frappe.msgprint(str(response_dict))

	def address_validation(self, credentials, add_doc, country_doc):
		from fedex.services.address_validation_service import FedexAddressValidationRequest
		avs_request = FedexAddressValidationRequest(credentials)
		if add_doc.state_rigpl is not None:
			state_doc = frappe.get_doc("State", add_doc.state)
		else:
			state_doc = ""
		if state_doc != "":
			state_code = state_doc.state_code
		else:
			state_code = ""
		address1 = avs_request.create_wsdl_object_of_type('AddressToValidate')
		address1.Address.StreetLines = [add_doc.address_line1, add_doc.address_line2]
		address1.Address.City = add_doc.city
		address1.Address.StateOrProvinceCode = state_code
		address1.Address.PostalCode = add_doc.pincode
		address1.Address.CountryCode = country_doc.code
		address1.Address.CountryName = add_doc.country
		address1.Address.Residential = add_doc.is_residential_address
		avs_request.add_address(address1)
		avs_request.send_request()
		response_dict = sobject_to_dict(avs_request.response)
		frappe.msgprint(str(response_dict))

	def get_required_docs(self):
		transporter_doc = frappe.get_doc("Transporters", self.shipment_forwarder)
		if transporter_doc.fedex_credentials != 1:
			frappe.throw(("{0} is not a Valid Fedex Account").format(self.shipment_forwarder))
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
		call_type.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER' #self.shipping_payment_by
		call_type.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = \
		    credentials.account_number 
			#self.config_obj.account_number if self.shipping_payment_by == "SENDER" else self.shipping_payment_account

		call_type.RequestedShipment.CustomsClearanceDetail.DutiesPayment.PaymentType = 'RECIPIENT' 
		#self.duties_payment_by
		#call_type.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor.ResponsibleParty.AccountNumber = \
		#	self.config_obj.account_number if self.duties_payment_by == "SENDER" else self.duties_payment_account
		return call_type	


	def set_shipper_info(self, call_type, ship_add_doc, credentials):
		from_country_doc = frappe.get_doc("Country", ship_add_doc.country)
		tin_no = ship_add_doc.gstin
		if ship_add_doc.state_rigpl is not None:
			state_doc = frappe.get_doc("State", ship_add_doc.state)
		else:
			state_doc = ""
		if state_doc != "":
			state_code = state_doc.state_code
		else:
			state_code = ""
		call_type.RequestedShipment.Shipper.AccountNumber = credentials.account_number
		call_type.RequestedShipment.Shipper.Contact.PersonName = ship_add_doc.address_title
		call_type.RequestedShipment.Shipper.Contact.CompanyName = ship_add_doc.address_title
		call_type.RequestedShipment.Shipper.Contact.PhoneNumber = ship_add_doc.phone
		call_type.RequestedShipment.Shipper.Address.StreetLines = [ship_add_doc.address_line1,\
			 ship_add_doc.address_line2]
		call_type.RequestedShipment.Shipper.Address.City = ship_add_doc.city
		call_type.RequestedShipment.Shipper.Address.StateOrProvinceCode = state_code
		call_type.RequestedShipment.Shipper.Address.PostalCode = ship_add_doc.pincode
		call_type.RequestedShipment.Shipper.Address.CountryCode = from_country_doc.code
		call_type.RequestedShipment.Shipper.Address.Residential = ship_add_doc.is_residential_address
		if tin_no != 'NA' and tin_no is not None:
			tin_details = call_type.create_wsdl_object_of_type('TaxpayerIdentification')
			tin_details.TinType.value = "BUSINESS_NATIONAL"
			tin_details.Number = tin_no
			call_type.RequestedShipment.Shipper.Tins = [tin_details]

	def set_recipient_info(self, call_type, ship_add_doc, credentials):
		to_country_doc = frappe.get_doc("Country", ship_add_doc.country)
		tin_no = ship_add_doc.gstin
		if ship_add_doc.state_rigpl is not None:
			state_doc = frappe.get_doc("State", ship_add_doc.state)
		else:
			state_doc = ""
		if state_doc != "":
			state_code = state_doc.state_code
		else:
			state_code = ""

		call_type.RequestedShipment.Recipient.Contact.PersonName = ship_add_doc.address_title
		call_type.RequestedShipment.Recipient.Contact.CompanyName = ship_add_doc.address_title
		call_type.RequestedShipment.Recipient.Contact.PhoneNumber = ship_add_doc.phone
		call_type.RequestedShipment.Recipient.Address.StreetLines = [ship_add_doc.address_line1, \
			ship_add_doc.address_line1]
		call_type.RequestedShipment.Recipient.Address.City = ship_add_doc.city
		call_type.RequestedShipment.Recipient.Address.StateOrProvinceCode = state_code
		call_type.RequestedShipment.Recipient.Address.PostalCode = ship_add_doc.pincode
		call_type.RequestedShipment.Recipient.Address.CountryCode = to_country_doc.code
		call_type.RequestedShipment.Recipient.Address.Residential = ship_add_doc.is_residential_address
		call_type.RequestedShipment.EdtRequestType = 'NONE' #Can be ALL or NONE
		call_type.RequestedShipment.FreightShipmentDetail.TotalHandlingUnits = self.total_handling_units
		if tin_no != 'NA' and tin_no is not None:
			tin_details = call_type.create_wsdl_object_of_type('TaxpayerIdentification')
			tin_details.TinType.value = "BUSINESS_NATIONAL"
			tin_details.Number = tin_no
			call_type.RequestedShipment.Recipient.Tins = [tin_details]


	def set_commercial_invoice_info(self, call_type):
		call_type.RequestedShipment.CustomsClearanceDetail.CommercialInvoice.Purpose = self.purpose
		#call_type.RequestedShipment.CustomsClearanceDetail.CommercialInvoice.CustomsInvoiceNumber = self.reference_docname
		call_type.RequestedShipment.ShippingDocumentSpecification.ShippingDocumentTypes = "COMMERCIAL_INVOICE"
		call_type.RequestedShipment.ShippingDocumentSpecification.CommercialInvoiceDetail.\
			Format.ImageType = "PDF"
		call_type.RequestedShipment.ShippingDocumentSpecification.CommercialInvoiceDetail.\
			Format.StockType = "PAPER_LETTER"
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
		'''
		# Adding references as required by label evaluation process
		for ref, field in {"P_O_NUMBER":"shipment_type", "DEPARTMENT_NUMBER":"octroi_payment_by"}.iteritems():
			ref_data = shipment.create_wsdl_object_of_type('CustomerReference')
			ref_data.CustomerReferenceType = ref
			ref_data.Value = doc.get(field)
			package.CustomerReferences.append(ref_data)
		'''
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
		
		if self.reference_doctype == 'Sales Invoice':
			doc = frappe.get_doc(self.reference_doctype, self.reference_docname)
			self.total_amount = doc.grand_total
			self.currency = doc.currency
			total_qty = 0
			for row in doc.items:
				total_qty += row.get("qty")
				hsn_doc = frappe.get_doc("GST HSN Code", row.get("cetsh_number"))
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
				"UnitPrice":{"Currency":doc.currency, "Amount":(doc.grand_total/total_qty)},
				"CustomsValue":{"Currency":doc.currency, "Amount":doc.grand_total}
			}
			shipment.RequestedShipment.CustomsClearanceDetail.Commodities.append(commodity_dict)
		else:
			frappe.throw("Currently only Booking Shipment is Available vide Sales Invoice")
			total_value = self.amount

	def set_email_notification(self, shipment, shipper_details, recipient_details):
		if self.fedex_notification:
			shipment.RequestedShipment.SpecialServicesRequested.EMailNotificationDetail.AggregationType = "PER_SHIPMENT"
			notify_mapper = {"Sender":"SHIPPER", "Recipient":"RECIPIENT", "Other-1":"OTHER", \
								"Other-2":"OTHER", "Other-3":"OTHER"}
			email_id_mapper = {"Sender":shipper_details, "Recipient":recipient_details, "Other-1":{}, \
								"Other-2":{}, "Other-3":{} }
			for row in doc.fedex_notification:
				notify_dict = {
					"EMailNotificationRecipientType":notify_mapper.get(row.notify_to, "SHIPPER"),
					"EMailAddress":email_id_mapper.get(row.notify_to, {}).get("email_id", row.email_id or ""),
					"NotificationEventsRequested":[ fedex_event for event, fedex_event in {"shipment":"ON_SHIPMENT", "delivery":"ON_DELIVERY", \
														"tendered":"ON_TENDER", "exception":"ON_EXCEPTION"}.items() if row.get(event)],
					"Format":"HTML",
					"Localization":{"LanguageCode":"EN", \
									"LocaleCode":email_id_mapper.get(row.notify_to, {}).get("country_code", "IN")}
				}
				shipment.RequestedShipment.SpecialServicesRequested.EMailNotificationDetail.Recipients.append(notify_dict)
	
	def location_service(self, credentials, from_address_doc, from_country_doc):
		from fedex.services.location_service import FedexSearchLocationRequest
		customer_transaction_id = "*** LocationService Request v3 using Python ***"  # Optional transaction_id
		location_request = FedexSearchLocationRequest(credentials, customer_transaction_id=customer_transaction_id)
		location_request.Constraints.RadiusDistance.Value = self.radius
		location_request.Constraints.RadiusDistance.Units = self.radius_uom
		location_request.Address.PostalCode = from_address_doc.pincode
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

	def set_package_details(self, pkg, shipment_response, tracking_id):
		pkg.shipment_response = shipment_response
		pkg.tracking_id = tracking_id

	@staticmethod
	def get_company_data(request_data, field_name):
		shipper_details = frappe.db.get_value("Address", request_data.get("shipper_id"), "*", as_dict=True)
		field_value = frappe.db.get_value("Company", shipper_details.get("company"), field_name)
		return shipper_details, field_value

	def schedule_pickup(self):
		request_data = json.loads(request_data)
		self.schedule_pickup_service(request_data)

	def schedule_pickup_service (self, request_data):
		shipper_details, closing_time = self.get_company_data(request_data, "closing_time")
		
		pickup_service = FedexCreatePickupRequest(credentials)
		pickup_service.OriginDetail.PickupLocation.Contact.PersonName = shipper_details.get("address_title")
		pickup_service.OriginDetail.PickupLocation.Contact.EMailAddress = shipper_details.get("email_id")
		pickup_service.OriginDetail.PickupLocation.Contact.CompanyName = shipper_details.get("company")
		pickup_service.OriginDetail.PickupLocation.Contact.PhoneNumber = shipper_details.get("phone")
		pickup_service.OriginDetail.PickupLocation.Address.StateOrProvinceCode = shipper_details.get("state_code")
		pickup_service.OriginDetail.PickupLocation.Address.PostalCode = shipper_details.get("pincode")
		pickup_service.OriginDetail.PickupLocation.Address.CountryCode = shipper_details.get("country_code")
		pickup_service.OriginDetail.PickupLocation.Address.StreetLines = [shipper_details.get("address_line1"),\
																	 shipper_details.get("address_line2")]
		pickup_service.OriginDetail.PickupLocation.Address.City = shipper_details.get("city")
		pickup_service.OriginDetail.PickupLocation.Address.Residential = True if shipper_details.get("is_residential_address") \
																			else False
		pickup_service.OriginDetail.PackageLocation = 'NONE'
		pickup_service.OriginDetail.ReadyTimestamp = get_datetime(request_data.get("ready_time")).replace(microsecond=0).isoformat()
		pickup_service.OriginDetail.CompanyCloseTime = closing_time if closing_time else '20:00:00'
		pickup_service.CarrierCode = 'FDXE'
		pickup_service.PackageCount = request_data.get("package_count")

		package_weight = pickup_service.create_wsdl_object_of_type('Weight')
		package_weight.Units = FedexController.uom_mapper.get(request_data.get("uom"))
		package_weight.Value = request_data.get("gross_weight")
		pickup_service.TotalWeight = package_weight

		pickup_service.send_request()
		if pickup_service.response.HighestSeverity not in ["SUCCESS", "NOTE", "WARNING"]:
			self.show_notification(pickup_service)
			frappe.throw(_('Pickup service scheduling failed.'))
		return { "response": pickup_service.response.HighestSeverity,
				  "pickup_id": pickup_service.response.PickupConfirmationNumber,
				  "location_no": pickup_service.response.Location
				}