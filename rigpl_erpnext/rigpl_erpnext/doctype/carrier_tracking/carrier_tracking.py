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

class CarrierTracking(Document):
	def validate(self):
		if self.document == "Sales Invoice":
			si_doc = frappe.get_doc("Sales Invoice",self.document_name)
			if self.carrier_name == si_doc.transporters and self.awb_number == si_doc.lr_no:
				self.invoice_integrity = 1
			else:
				self.invoice_integrity = 0

		if self.status == "Delivered":
			self.docstatus = 1

		if self.invoice_integrity != 1:
			if self.posted_to_shipway == 1:
				si_doc = frappe.get_doc("Sales Invoice", self.document_name)
				si_awb = re.sub('[^A-Za-z0-9]+', '', str(si_doc.lr_no))
				if re.sub('[^A-Za-z0-9]+', '', str(self.awb_number)) != si_awb or si_doc.transporters != self.carrier_name:
					create_new_carrier_track(si_doc, frappe)
					self.docstatus = 1
			else:
				self.awb_number = si_doc.lr_no
				self.carrier_name = si_doc.transporters
		'''
		Check Carrier and LR No with Sales Invoice
		Order ID = ID of the Tracking Number (DONE)
		Don't allow if the document is NOT SAVE (DONE)
		Don't allow multiple AWB numbers to be posted to Shipway instead just pull the data 
		from Shipway (TOO COMPLEX since we cannot change shipment data via API)
		Validation check the Document Number with DOCTYPE and AWB number should not 
		repeat with Same Carrier (TOO COMPLEX since we cannot change shipment data via API)
		'''

	def pushdata (self):
		pushOrderData (self)


	def getdata(self):
		getOrderShipmentDetails(self)