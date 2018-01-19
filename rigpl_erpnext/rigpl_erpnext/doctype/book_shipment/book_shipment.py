# -*- coding: utf-8 -*-
# Copyright (c) 2018, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import fedex
import datetime
from frappe.model.document import Document

class BookShipment(Document):
	def validate(self):
		pass

	def test(self):
		transporter_doc = frappe.get_doc("Transporters", self.shipment_forwarder)
		to_address_doc = frappe.get_doc("Address", self.to_address)
		to_country_doc = frappe.get_doc("Country", to_address_doc.country)
		contact_doc = frappe.get_doc("Contact", self.contact_person)
		from_address_doc = frappe.get_doc("Address", self.from_address)
		from_country_doc = frappe.get_doc("Country", from_address_doc.country)
		credentials = self.get_fedex_credentials(transporter_doc)
		#self.address_validation(credentials, to_address_doc, to_country_doc)
		#self.availabiltiy_commitment(credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc)
		#self.validate_postal_request(credentials, to_address_doc, to_country_doc) #This one seems NOT WORKING
		#self.location_service(credentials, from_address_doc, from_country_doc)
		#self.rate_service(credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, transporter_doc)
		self.create_shipment(credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, \
			transporter_doc, contact_doc)
		#self.delete_shipment(credentials, transporter_doc)

	def get_fedex_credentials(self, transporter_doc):
		from fedex.config import FedexConfig
		credentials = FedexConfig(key = transporter_doc.fedex_key,
				password = transporter_doc.fedex_password,
				account_number = transporter_doc.fedex_account_number,
				meter_number = transporter_doc.fedex_meter_number,
				use_test_server = transporter_doc.is_test_server)
		return credentials

	def address_validation(self, credentials, add_doc, country_doc):
		from fedex.services.address_validation_service import FedexAddressValidationRequest
		avs_request = FedexAddressValidationRequest(credentials)
		address1 = avs_request.create_wsdl_object_of_type('AddressToValidate')
		address1.Address.StreetLines = [add_doc.address_line1, add_doc.address_line2]
		address1.Address.City = add_doc.city
		address1.Address.StateOrProvinceCode = add_doc.state
		address1.Address.PostalCode = add_doc.pincode
		address1.Address.CountryCode = country_doc.code
		address1.Address.CountryName = add_doc.country
		address1.Address.Residential = add_doc.is_residential_address
		frappe.msgprint(str(address1))
		avs_request.add_address(address1)
		avs_request.send_request()
		frappe.msgprint(avs_request.response)

	def availabiltiy_commitment(self, credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc):
		from fedex.services.availability_commitment_service import FedexAvailabilityCommitmentRequest
		avc_request = FedexAvailabilityCommitmentRequest(credentials)
		avc_request.Origin.PostalCode = from_address_doc.pincode
		avc_request.Origin.CountryCode = from_country_doc.code
		avc_request.Destination.PostalCode = to_address_doc.pincode
		avc_request.Destination.CountryCode = to_country_doc.code
		avc_request.ShipDate = datetime.date.today().isoformat()
		avc_request.send_request()
		frappe.msgprint(str(avc_request.response))

	def validate_postal_request(self, credentials, to_address_doc, to_country_doc):
		#This service failed the TEST Check AGAIN
		from fedex.services.country_service import FedexValidatePostalRequest
		# We're using the FedexConfig object from example_config.py in this dir.
		customer_transaction_id = "*** ValidatePostal Request v4 using Python ***"  # Optional transaction_id
		inquiry = FedexValidatePostalRequest(credentials, customer_transaction_id=customer_transaction_id)
		inquiry.Address.PostalCode = to_address_doc.pincode
		inquiry.Address.CountryCode = to_country_doc.code
		inquiry.Address.StreetLines = [to_address_doc.address_line1, to_address_doc.address_line2]
		inquiry.Address.City = to_address_doc.city
		inquiry.Address.StateOrProvinceCode = to_address_doc.state
		inquiry.send_request()
		frappe.msgprint(str(inquiry.response))

	def location_service(self, credentials, from_address_doc, from_country_doc):
		#Todo Make the Radius and Units selectable in a Utility
		'''
		Locations Service
		The Locations Service WSDL searches for, and returns, the addresses of the nearest FedEx package
		drop-off locations, including FedEx Office® Print and Ship Center, Drop Box and Ship and 
		Get Locker locations.
		'''
		from fedex.services.location_service import FedexSearchLocationRequest
		from fedex.tools.conversion import sobject_to_dict
		customer_transaction_id = "*** LocationService Request v3 using Python ***"  # Optional transaction_id
		location_request = FedexSearchLocationRequest(credentials, customer_transaction_id=customer_transaction_id)
		location_request.Constraints.RadiusDistance.Value = 15
		location_request.Constraints.RadiusDistance.Units = "KM"
		location_request.Address.PostalCode = from_address_doc.pincode
		location_request.Address.CountryCode = from_country_doc.code
		location_request.send_request()
		frappe.msgprint(str(location_request.response))

	def rate_service(self, credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, transporter_doc):
		from fedex.services.rate_service import FedexRateServiceRequest
		from fedex.tools.conversion import sobject_to_dict
		customer_transaction_id = "*** RateService Request v18 using Python ***"  # Optional transaction_id
		rate_request = FedexRateServiceRequest(credentials, customer_transaction_id=customer_transaction_id)
		rate_request.ReturnTransitAndCommit = True
		rate_request.RequestedShipment.DropoffType = 'REGULAR_PICKUP'
		rate_request.RequestedShipment.ServiceType = transporter_doc.fedex_service_code
		rate_request.RequestedShipment.PackagingType = 'YOUR_PACKAGING'
		rate_request.RequestedShipment.Shipper.Address.PostalCode = from_address_doc.pincode
		rate_request.RequestedShipment.Shipper.Address.CountryCode = from_country_doc.code
		rate_request.RequestedShipment.Shipper.Address.Residential = from_address_doc.is_residential_address
		rate_request.RequestedShipment.Recipient.Address.PostalCode = to_address_doc.pincode
		rate_request.RequestedShipment.Recipient.Address.CountryCode = to_country_doc.code
		rate_request.RequestedShipment.EdtRequestType = 'NONE' #Can be ALL or NONE
		rate_request.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER'
		package1_weight = rate_request.create_wsdl_object_of_type('Weight')
		package1_weight.Value = 1.0
		package1_weight.Units = "KG"
		package1 = rate_request.create_wsdl_object_of_type('RequestedPackageLineItem')
		package1.Weight = package1_weight
		package1.PhysicalPackaging = 'BOX'
		package1.GroupPackageCount = 1
		rate_request.add_package(package1)
		rate_request.send_request()
		frappe.msgprint(str(rate_request.response))

	def rate_service_freight(self, credentials, from_address_doc, to_address_doc, from_country_doc, to_country_doc, transporter_doc):
		from fedex.services.rate_service import FedexRateServiceRequest
		from fedex.tools.conversion import sobject_to_dict
		customer_transaction_id = "*** RateService Request v18 using Python ***"  # Optional transaction_id
		rate_request = FedexRateServiceRequest(credentials, customer_transaction_id=customer_transaction_id)
		rate_request.ReturnTransitAndCommit = True
		rate_request.RequestedShipment.DropoffType = 'REGULAR_PICKUP'
		rate_request.RequestedShipment.ServiceType = transporter_doc.fedex_service_code
		rate_request.RequestedShipment.PackagingType = 'YOUR_PACKAGING'
		rate_request.RequestedShipment.FreightShipmentDetail.TotalHandlingUnits = 1
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightAccountNumber = credentials.freight_account_number

		#Shipper
		rate_request.RequestedShipment.Shipper.AccountNumber = credentials.freight_account_number
		rate_request.RequestedShipment.Shipper.Contact.PersonName = 'Sender Name'
		rate_request.RequestedShipment.Shipper.Contact.CompanyName = 'Some Company'
		rate_request.RequestedShipment.Shipper.Contact.PhoneNumber = '9012638716'
		rate_request.RequestedShipment.Shipper.Address.StreetLines = ['2000 Freight LTL Testing']
		rate_request.RequestedShipment.Shipper.Address.City = 'Harrison'
		rate_request.RequestedShipment.Shipper.Address.StateOrProvinceCode = 'AR'
		rate_request.RequestedShipment.Shipper.Address.PostalCode = from_address_doc.pincode
		rate_request.RequestedShipment.Shipper.Address.CountryCode = from_country_doc.code

		#Recipient
		rate_request.RequestedShipment.Recipient.Address.City = 'Harrison'
		rate_request.RequestedShipment.Recipient.Address.StateOrProvinceCode = 'AR'
		rate_request.RequestedShipment.Recipient.Address.PostalCode = to_address_doc.pincode
		rate_request.RequestedShipment.Recipient.Address.CountryCode = to_country_doc.code
		rate_request.RequestedShipment.Shipper.Address.Residential = from_address_doc.is_residential_address

		#Payment
		payment = rate_request.create_wsdl_object_of_type('Payment')
		rate_request.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER'
		payment.Payor.ResponsibleParty = rate_request.RequestedShipment.Shipper
		rate_request.RequestedShipment.ShippingChargesPayment = payment

		# include estimated duties and taxes in rate quote, can be ALL or NONE
		rate_request.RequestedShipment.EdtRequestType = 'NONE'

		# note: in order for this to work in test, you may need to use the
		# specially provided LTL addresses emailed to you when signing up.
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress.Contact.PersonName = 'Sender Name'
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress.Contact.CompanyName = 'Some Company'
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress.Contact.PhoneNumber = '9012638716'
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress.Address.StreetLines = [
		    '2000 Freight LTL Testing']
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress.Address.City = 'Harrison'
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress.Address.StateOrProvinceCode = 'AR'
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress.Address.PostalCode = '72601'
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress.Address.CountryCode = 'US'
		rate_request.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress.Address.Residential = False

		spec = rate_request.create_wsdl_object_of_type('ShippingDocumentSpecification')

		spec.ShippingDocumentTypes = [spec.CertificateOfOrigin]

		rate_request.RequestedShipment.ShippingDocumentSpecification = spec

		role = rate_request.create_wsdl_object_of_type('FreightShipmentRoleType')
		rate_request.RequestedShipment.FreightShipmentDetail.Role = role.SHIPPER

		# Designates the terms of the "collect" payment for a Freight
		# Shipment. Can be NON_RECOURSE_SHIPPER_SIGNED or STANDARD
		rate_request.RequestedShipment.FreightShipmentDetail.CollectTermsType = 'STANDARD'

		package1_weight = rate_request.create_wsdl_object_of_type('Weight')
		package1_weight.Value = 500.0
		package1_weight.Units = "LB"

		rate_request.RequestedShipment.FreightShipmentDetail.PalletWeight = package1_weight

		package1 = rate_request.create_wsdl_object_of_type('FreightShipmentLineItem')
		package1.Weight = package1_weight
		package1.Packaging = 'PALLET'
		package1.Description = 'Products'
		package1.FreightClass = 'CLASS_500'

		rate_request.RequestedShipment.FreightShipmentDetail.LineItems = package1
		rate_request.send_request()
		frappe.msgprint(str(rate_request.response))

	def create_shipment(self, credentials, from_address_doc, to_address_doc, from_country_doc, \
			to_country_doc, transporter_doc, contact_doc):

		from fedex.services.ship_service import FedexProcessShipmentRequest
		GENERATE_IMAGE_TYPE = 'PDF'
		customer_transaction_id = "*** ShipService Request v17 using Python ***"  # Optional transaction_id
		shipment = FedexProcessShipmentRequest(credentials, customer_transaction_id=customer_transaction_id)

		# This is very generalized, top-level information.
		# REGULAR_PICKUP, REQUEST_COURIER, DROP_BOX, BUSINESS_SERVICE_CENTER or STATION
		shipment.RequestedShipment.DropoffType = 'REGULAR_PICKUP'

		# See page 355 in WS_ShipService.pdf for a full list. Here are the common ones:
		# STANDARD_OVERNIGHT, PRIORITY_OVERNIGHT, FEDEX_GROUND, FEDEX_EXPRESS_SAVER,
		# FEDEX_2_DAY, INTERNATIONAL_PRIORITY, SAME_DAY, INTERNATIONAL_ECONOMY
		shipment.RequestedShipment.ServiceType = transporter_doc.fedex_service_code

		# What kind of package this will be shipped in.
		# FEDEX_BOX, FEDEX_PAK, FEDEX_TUBE, YOUR_PACKAGING, FEDEX_ENVELOPE
		shipment.RequestedShipment.PackagingType = 'YOUR PACKAGING'

		# Shipper contact info.
		shipment.RequestedShipment.Shipper.Contact.PersonName = from_address_doc.address_title
		shipment.RequestedShipment.Shipper.Contact.CompanyName = from_address_doc.address_title
		shipment.RequestedShipment.Shipper.Contact.PhoneNumber = from_address_doc.phone

		# Shipper address.
		shipment.RequestedShipment.Shipper.Address.StreetLines = [from_address_doc.address_line1, from_address_doc.address_line2]
		shipment.RequestedShipment.Shipper.Address.City = from_address_doc.city
		shipment.RequestedShipment.Shipper.Address.StateOrProvinceCode = from_address_doc.state
		shipment.RequestedShipment.Shipper.Address.PostalCode = from_address_doc.pincode
		shipment.RequestedShipment.Shipper.Address.CountryCode = from_country_doc.code
		shipment.RequestedShipment.Shipper.Address.Residential = from_address_doc.is_residential_address

		# Recipient contact info.
		shipment.RequestedShipment.Recipient.Contact.PersonName = str(contact_doc.salutation) + \
			" " + contact_doc.first_name + " " + str(contact_doc.last_name)
		shipment.RequestedShipment.Recipient.Contact.CompanyName = to_address_doc.address_title
		shipment.RequestedShipment.Recipient.Contact.PhoneNumber = str(to_address_doc.phone) + " " + str(contact_doc.mobile_no)

		# Recipient address
		shipment.RequestedShipment.Recipient.Address.StreetLines = [to_address_doc.address_line1, to_address_doc.address_line2]
		shipment.RequestedShipment.Recipient.Address.City = to_address_doc.city
		shipment.RequestedShipment.Recipient.Address.StateOrProvinceCode = to_address_doc.state
		shipment.RequestedShipment.Recipient.Address.PostalCode = to_address_doc.pincode
		shipment.RequestedShipment.Recipient.Address.CountryCode = to_country_doc.code
		# This is needed to ensure an accurate rate quote with the response. Use AddressValidation to get ResidentialStatus
		shipment.RequestedShipment.Recipient.Address.Residential = to_address_doc.is_residential_address
		shipment.RequestedShipment.EdtRequestType = 'NONE'

		# Senders account information
		shipment.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = credentials.account_number

		# Who pays for the shipment?
		# RECIPIENT, SENDER or THIRD_PARTY
		shipment.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER'

		# Specifies the label type to be returned.
		# LABEL_DATA_ONLY or COMMON2D
		shipment.RequestedShipment.LabelSpecification.LabelFormatType = 'COMMON2D'

		# Specifies which format the label file will be sent to you in.
		# DPL, EPL2, PDF, PNG, ZPLII
		shipment.RequestedShipment.LabelSpecification.ImageType = GENERATE_IMAGE_TYPE

		# To use doctab stocks, you must change ImageType above to one of the
		# label printer formats (ZPLII, EPL2, DPL).
		# See documentation for paper types, there quite a few.
		shipment.RequestedShipment.LabelSpecification.LabelStockType = 'PAPER_7X4.75'

		# This indicates if the top or bottom of the label comes out of the 
		# printer first.
		# BOTTOM_EDGE_OF_TEXT_FIRST or TOP_EDGE_OF_TEXT_FIRST
		# Timestamp in YYYY-MM-DDThh:mm:ss format, e.g. 2002-05-30T09:00:00
		shipment.RequestedShipment.ShipTimestamp = datetime.datetime.now().replace(microsecond=0).isoformat()

		# BOTTOM_EDGE_OF_TEXT_FIRST, TOP_EDGE_OF_TEXT_FIRST
		shipment.RequestedShipment.LabelSpecification.LabelPrintingOrientation = 'TOP_EDGE_OF_TEXT_FIRST'

		# Delete the flags we don't want.
		# Can be SHIPPING_LABEL_FIRST, SHIPPING_LABEL_LAST or delete
		if hasattr(shipment.RequestedShipment.LabelSpecification, 'LabelOrder'):
		    del shipment.RequestedShipment.LabelSpecification.LabelOrder  # Delete, not using.

		# Create Weight, in pounds.
		package1_weight = shipment.create_wsdl_object_of_type('Weight')
		package1_weight.Value = 1.0
		package1_weight.Units = "LB"

		# Insured Value
		# package1_insure = shipment.create_wsdl_object_of_type('Money')
		# package1_insure.Currency = 'USD'
		# package1_insure.Amount = 1.0

		# Create PackageLineItem
		package1 = shipment.create_wsdl_object_of_type('RequestedPackageLineItem')
		# BAG, BARREL, BASKET, BOX, BUCKET, BUNDLE, CARTON, CASE, CONTAINER, ENVELOPE etc..
		package1.PhysicalPackaging = 'ENVELOPE'
		package1.Weight = package1_weight

		# Add Insured and Total Insured values.
		# package1.InsuredValue = package1_insure
		# shipment.RequestedShipment.TotalInsuredValue = package1_insure

		# Add customer reference
		# customer_reference = shipment.create_wsdl_object_of_type('CustomerReference')
		# customer_reference.CustomerReferenceType="CUSTOMER_REFERENCE"
		# customer_reference.Value = "your customer reference number"
		# package1.CustomerReferences.append(customer_reference)

		# Add department number
		# department_number = shipment.create_wsdl_object_of_type('CustomerReference')
		# department_number.CustomerReferenceType="DEPARTMENT_NUMBER"
		# department_number.Value = "your department number"
		# package1.CustomerReferences.append(department_number)

		# Add invoice number
		# invoice_number = shipment.create_wsdl_object_of_type('CustomerReference')
		# invoice_number.CustomerReferenceType="INVOICE_NUMBER"
		# invoice_number.Value = "your invoice number"
		# package1.CustomerReferences.append(invoice_number)

		# Add a signature option for the package using SpecialServicesRequested or comment out.
		# SpecialServiceTypes can be APPOINTMENT_DELIVERY, COD, DANGEROUS_GOODS, DRY_ICE, SIGNATURE_OPTION etc..
		package1.SpecialServicesRequested.SpecialServiceTypes = 'SIGNATURE_OPTION'
		# SignatureOptionType can be ADULT, DIRECT, INDIRECT, NO_SIGNATURE_REQUIRED, SERVICE_DEFAULT
		package1.SpecialServicesRequested.SignatureOptionDetail.OptionType = 'SERVICE_DEFAULT'

		# Un-comment this to see the other variables you may set on a package.
		# print(package1)

		# This adds the RequestedPackageLineItem WSDL object to the shipment. It
		# increments the package count and total weight of the shipment for you.
		shipment.add_package(package1)

		# If you'd like to see some documentation on the ship service WSDL, un-comment
		# this line. (Spammy).
		# print(shipment.client)

		# Un-comment this to see your complete, ready-to-send request as it stands
		# before it is actually sent. This is useful for seeing what values you can
		# change.
		# print(shipment.RequestedShipment)
		# print(shipment.ClientDetail)
		# print(shipment.TransactionDetail)

		# If you want to make sure that all of your entered details are valid, you
		# can call this and parse it just like you would via send_request(). If
		# shipment.response.HighestSeverity == "SUCCESS", your shipment is valid.
		# print(shipment.send_validation_request())

		# Fires off the request, sets the 'response' attribute on the object.
		shipment.send_request()

		# This will show the reply to your shipment being sent. You can access the
		# attributes through the response attribute on the request object. This is
		# good to un-comment to see the variables returned by the Fedex reply.
		# print(shipment.response)

		# This will convert the response to a python dict object. To
		# make it easier to work with. Also see basic_sobject_to_dict, it's faster but lacks options.
		# from fedex.tools.response_tools import sobject_to_dict
		# response_dict = sobject_to_dict(shipment.response)
		# response_dict['CompletedShipmentDetail']['CompletedPackageDetails'][0]['Label']['Parts'][0]['Image'] = ''
		# print(response_dict)  # Image is empty string for display purposes.

		# This will dump the response data dict to json.
		# from fedex.tools.response_tools import sobject_to_json
		# print(sobject_to_json(shipment.response))

		# Here is the overall end result of the query.
		frappe.msgprint(str(shipment.response))

		# Getting the tracking number from the new shipment.
		print("Tracking #: {}"
		      "".format(shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].TrackingIds[0].TrackingNumber))

		# Net shipping costs. Only show if available. Sometimes sandbox will not include this in the response.
		CompletedPackageDetails = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0]
		if hasattr(CompletedPackageDetails, 'PackageRating'):
		    print("Net Shipping Cost (US$): {}"
		          "".format(CompletedPackageDetails.PackageRating.PackageRateDetails[0].NetCharge.Amount))
		else:
		    print('WARNING: Unable to get shipping rate.')

		# Get the label image in ASCII format from the reply. Note the list indices
		# we're using. You'll need to adjust or iterate through these if your shipment
		# has multiple packages.

		ascii_label_data = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].Label.Parts[0].Image

		# Convert the ASCII data to binary.
		label_binary_data = binascii.a2b_base64(ascii_label_data)

		"""
		This is an example of how to dump a label to a local file.
		"""
		# This will be the file we write the label out to.
		out_path = 'example_shipment_label.%s' % GENERATE_IMAGE_TYPE.lower()
		print("Writing to file {}".format(out_path))
		out_file = open(out_path, 'wb')
		out_file.write(label_binary_data)
		out_file.close()

		"""
		This is an example of how to print the label to a serial printer. This will not
		work for all label printers, consult your printer's documentation for more
		details on what formats it can accept.
		"""
		# Pipe the binary directly to the label printer. Works under Linux
		# without requiring PySerial. This WILL NOT work on other platforms.
		# label_printer = open("/dev/ttyS0", "w")
		# label_printer.write(label_binary_data)
		# label_printer.close()

		"""
		This is a potential cross-platform solution using pySerial. This has not been
		tested in a long time and may or may not work. For Windows, Mac, and other
		platforms, you may want to go this route.
		"""
		# import serial
		# label_printer = serial.Serial(0)
		# print("SELECTED SERIAL PORT: "+ label_printer.portstr)
		# label_printer.write(label_binary_data)
		# label_printer.close()

	def create_shipment_freight():
		from fedex.services.ship_service import FedexProcessShipmentRequest

		# What kind of file do you want this example to generate?
		# Valid choices for this example are PDF, PNG
		GENERATE_IMAGE_TYPE = 'PDF'

		# Un-comment to see the response from Fedex printed in stdout.
		logging.basicConfig(stream=sys.stdout, level=logging.INFO)

		# NOTE: A VALID 'freight_account_number' REQUIRED IN YOUR 'CONFIB_OBJ' FOR THIS SERVICE TO WORK.
		# OTHERWISE YOU WILL GET FEDEX FREIGHT OR ASSOCIATED ADDRESS IS REQUIRED, ERROR 3619.

		# This is the object that will be handling our freight shipment request.
		# We're using the FedexConfig object from example_config.py in this dir.
		shipment = FedexProcessShipmentRequest(CONFIG_OBJ)
		shipment.RequestedShipment.DropoffType = 'REGULAR_PICKUP'
		shipment.RequestedShipment.ServiceType = 'FEDEX_FREIGHT_ECONOMY'
		shipment.RequestedShipment.PackagingType = 'YOUR_PACKAGING'

		shipment.RequestedShipment.FreightShipmentDetail.FedExFreightAccountNumber = CONFIG_OBJ.freight_account_number

		# Shipper contact info.
		shipment.RequestedShipment.Shipper.Contact.PersonName = 'Sender Name'
		shipment.RequestedShipment.Shipper.Contact.CompanyName = 'Some Company'
		shipment.RequestedShipment.Shipper.Contact.PhoneNumber = '9012638716'

		# Shipper address.
		shipment.RequestedShipment.Shipper.Address.StreetLines = ['1202 Chalet Ln']
		shipment.RequestedShipment.Shipper.Address.City = 'Harrison'
		shipment.RequestedShipment.Shipper.Address.StateOrProvinceCode = 'AR'
		shipment.RequestedShipment.Shipper.Address.PostalCode = '72601'
		shipment.RequestedShipment.Shipper.Address.CountryCode = 'US'
		shipment.RequestedShipment.Shipper.Address.Residential = True

		# Recipient contact info.
		shipment.RequestedShipment.Recipient.Contact.PersonName = 'Recipient Name'
		shipment.RequestedShipment.Recipient.Contact.CompanyName = 'Recipient Company'
		shipment.RequestedShipment.Recipient.Contact.PhoneNumber = '9012637906'

		# Recipient address
		shipment.RequestedShipment.Recipient.Address.StreetLines = ['2000 Freight LTL Testing']
		shipment.RequestedShipment.Recipient.Address.City = 'Harrison'
		shipment.RequestedShipment.Recipient.Address.StateOrProvinceCode = 'AR'
		shipment.RequestedShipment.Recipient.Address.PostalCode = '72601'
		shipment.RequestedShipment.Recipient.Address.CountryCode = 'US'

		# This is needed to ensure an accurate rate quote with the response.
		shipment.RequestedShipment.Recipient.Address.Residential = False
		shipment.RequestedShipment.FreightShipmentDetail.TotalHandlingUnits = 1
		shipment.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = \
		    CONFIG_OBJ.freight_account_number

		billing_contact_address = shipment.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress

		billing_contact_address.Contact.PersonName = 'Sender Name'
		billing_contact_address.Contact.CompanyName = 'Some Company'
		billing_contact_address.Contact.PhoneNumber = '9012638716'

		billing_contact_address.Address.StreetLines = ['2000 Freight LTL Testing']
		billing_contact_address.Address.City = 'Harrison'
		billing_contact_address.Address.StateOrProvinceCode = 'AR'
		billing_contact_address.Address.PostalCode = '72601'
		billing_contact_address.Address.CountryCode = 'US'
		billing_contact_address.Address.Residential = False
		spec = shipment.create_wsdl_object_of_type('ShippingDocumentSpecification')

		spec.ShippingDocumentTypes = [spec.CertificateOfOrigin]
		# shipment.RequestedShipment.ShippingDocumentSpecification = spec

		role = shipment.create_wsdl_object_of_type('FreightShipmentRoleType')

		shipment.RequestedShipment.FreightShipmentDetail.Role = role.SHIPPER
		shipment.RequestedShipment.FreightShipmentDetail.CollectTermsType = 'STANDARD'

		# Specifies the label type to be returned.
		shipment.RequestedShipment.LabelSpecification.LabelFormatType = 'FEDEX_FREIGHT_STRAIGHT_BILL_OF_LADING'

		# Specifies which format the label file will be sent to you in.
		# DPL, EPL2, PDF, PNG, ZPLII
		shipment.RequestedShipment.LabelSpecification.ImageType = 'PDF'

		# To use doctab stocks, you must change ImageType above to one of the
		# label printer formats (ZPLII, EPL2, DPL).
		# See documentation for paper types, there quite a few.
		shipment.RequestedShipment.LabelSpecification.LabelStockType = 'PAPER_LETTER'

		# This indicates if the top or bottom of the label comes out of the 
		# printer first.
		# BOTTOM_EDGE_OF_TEXT_FIRST or TOP_EDGE_OF_TEXT_FIRST
		shipment.RequestedShipment.LabelSpecification.LabelPrintingOrientation = 'BOTTOM_EDGE_OF_TEXT_FIRST'
		shipment.RequestedShipment.EdtRequestType = 'NONE'

		# Delete the flags we don't want.
		# Can be SHIPPING_LABEL_FIRST, SHIPPING_LABEL_LAST or delete
		if hasattr(shipment.RequestedShipment.LabelSpecification, 'LabelOrder'):
		    del shipment.RequestedShipment.LabelSpecification.LabelOrder  # Delete, not using.

		package1_weight = shipment.create_wsdl_object_of_type('Weight')
		package1_weight.Value = 500.0
		package1_weight.Units = "LB"

		shipment.RequestedShipment.FreightShipmentDetail.PalletWeight = package1_weight

		package1 = shipment.create_wsdl_object_of_type('FreightShipmentLineItem')
		package1.Weight = package1_weight
		package1.Packaging = 'PALLET'
		package1.Description = 'Products'
		package1.FreightClass = 'CLASS_500'
		package1.HazardousMaterials = None
		package1.Pieces = 12

		shipment.RequestedShipment.FreightShipmentDetail.LineItems = package1

		# If you'd like to see some documentation on the ship service WSDL, un-comment
		# this line. (Spammy).
		# print(shipment.client)

		# Un-comment this to see your complete, ready-to-send request as it stands
		# before it is actually sent. This is useful for seeing what values you can
		# change.
		# print(shipment.RequestedShipment)

		# If you want to make sure that all of your entered details are valid, you
		# can call this and parse it just like you would via send_request(). If
		# shipment.response.HighestSeverity == "SUCCESS", your shipment is valid.
		# shipment.send_validation_request()

		# Fires off the request, sets the 'response' attribute on the object.
		shipment.send_request()

		# This will show the reply to your shipment being sent. You can access the
		# attributes through the response attribute on the request object. This is
		# good to un-comment to see the variables returned by the Fedex reply.
		# print(shipment.response)

		# This will convert the response to a python dict object. To
		# make it easier to work with. Also see basic_sobject_to_dict, it's faster but lacks options.
		# from fedex.tools.response_tools import sobject_to_dict
		# response_dict = sobject_to_dict(shipment.response)
		# response_dict['CompletedShipmentDetail']['ShipmentDocuments'][0]['Parts'][0]['Image'] = ''
		# print(response_dict)  # Image is empty string for display purposes.

		# This will dump the response data dict to json.
		# from fedex.tools.response_tools import sobject_to_json
		# print(sobject_to_json(shipment.response))

		# Here is the overall end result of the query.
		print("HighestSeverity: {}".format(shipment.response.HighestSeverity))

		# Getting the tracking number from the new shipment.
		print("Tracking #: {}"
		      "".format(shipment.response.CompletedShipmentDetail.MasterTrackingId.TrackingNumber))

		# Net shipping costs.
		amount = shipment.response.CompletedShipmentDetail.ShipmentRating.ShipmentRateDetails[0].TotalNetCharge.Amount
		print("Net Shipping Cost (US$): {}".format(amount))

		# # Get the label image in ASCII format from the reply. Note the list indices
		# we're using. You'll need to adjust or iterate through these if your shipment
		# has multiple packages.

		ascii_label_data = shipment.response.CompletedShipmentDetail.ShipmentDocuments[0].Parts[0].Image

		# Convert the ASCII data to binary.
		label_binary_data = binascii.a2b_base64(ascii_label_data)

		"""
		This is an example of how to dump a label to a local file.
		"""
		# This will be the file we write the label out to.
		out_path = 'example_freight_shipment_label.%s' % GENERATE_IMAGE_TYPE.lower()
		print("Writing to file {}".format(out_path))
		out_file = open(out_path, 'wb')
		out_file.write(label_binary_data)
		out_file.close()

		"""
		This is an example of how to print the label to a serial printer. This will not
		work for all label printers, consult your printer's documentation for more
		details on what formats it can accept.
		"""
		# Pipe the binary directly to the label printer. Works under Linux
		# without requiring PySerial. This WILL NOT work on other platforms.
		# label_printer = open("/dev/ttyS0", "w")
		# label_printer.write(label_binary_data)
		# label_printer.close()

		"""
		This is a potential cross-platform solution using pySerial. This has not been
		tested in a long time and may or may not work. For Windows, Mac, and other
		platforms, you may want to go this route.
		"""
		# import serial
		# label_printer = serial.Serial(0)
		# print("SELECTED SERIAL PORT: "+ label_printer.portstr)
		# label_printer.write(label_binary_data)
		# label_printer.close()

	def delete_shipment(self, credentials, transporter_doc):
		from fedex.services.ship_service import FedexDeleteShipmentRequest
		from fedex.base_service import FedexError
		del_request = FedexDeleteShipmentRequest(credentials)

		# Either delete all packages in a shipment, or delete an individual package.
		# Docs say this isn't required, but the WSDL won't validate without it.
		# DELETE_ALL_PACKAGES, DELETE_ONE_PACKAGE
		del_request.DeletionControlType = "DELETE_ALL_PACKAGES"

		# The tracking number of the shipment to delete.
		del_request.TrackingId.TrackingNumber = self.tracking_number  # '111111111111' will also not delete

		# What kind of shipment the tracking number used.
		# Docs say this isn't required, but the WSDL won't validate without it.
		# EXPRESS, GROUND, or USPS
		del_request.TrackingId.TrackingIdType = transporter_doc.type_of_service
		# Fires off the request, sets the 'response' attribute on the object.
		try:
		    del_request.send_request()
		except FedexError as e:
		    if 'Unable to retrieve record' in str(e):
		        print "WARNING: Unable to delete the shipment with the provided tracking number."
		    else:
		        print(e)

		# See the response printed out.
		# print(del_request.response)

		# This will convert the response to a python dict object. To
		# make it easier to work with.
		# from fedex.tools.response_tools import basic_sobject_to_dict
		# print(basic_sobject_to_dict(del_request.response))

		# This will dump the response data dict to json.
		# from fedex.tools.response_tools import sobject_to_json
		# print(sobject_to_json(del_request.response))

		# Here is the overall end result of the query.
		frappe.msgprint(str(del_request.response))