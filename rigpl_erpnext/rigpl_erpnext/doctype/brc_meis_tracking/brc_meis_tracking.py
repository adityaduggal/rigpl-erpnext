# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
import re
from frappe.model.document import Document
from frappe.utils import getdate, add_days
from rigpl_erpnext.rigpl_erpnext.validations.employee import validate_pan
from rigpl_erpnext.utils.other_utils import validate_ifsc_code, validate_brc_no


class BRCMEISTracking(Document):
	def validate(self):
		self.validate_fields()

	def on_submit(self):
		if self.brc_status == "BRC Pending":
			frappe.throw("BRC Pending, Cannot Submit {}".format(self.name))
		if self.meis_status not in ["MEIS Claimed", "MEIS Expired", "MEIS Not Applicable"]:
			frappe.throw("MEIS Scheme Pending hence Cannot Submit {}".format(self.name))

	def meis_validate(self):
		if self.meis_authorization_no:
			if len(str(self.meis_authorization_no)) != 10:
				frappe.throw("MEIS Authorization No should be of 10 Digits")
			p = re.compile("[0-9]{10}")
			if not p.match(str(self.meis_authorization_no)):
				frappe.throw("Invalid MEIS Authorization No, MEIS Authorization \
					No can only have Digits")
			if not self.meis_date:
				frappe.throw("MEIS Date is Mandatory")
			else:
				if self.meis_date < self.brc_date:
					frappe.throw("MEIS Date cannot be before BRC Date")
			self.meis_status = "MEIS Claimed"
			self.meis_reference_type = "Journal Entry"
			if not self.meis_reference_name:
				frappe.throw("Enter the JV# for the entry of MEIS")
			else:
				self.meis_amount = frappe.get_value("Journal Entry", self.meis_reference_name, "total_debit")
			self.docstatus = 1

	def validate_fields(self):
		if self.brc_status == "BRC Issued":
			self.meis_validate()
		elif self.brc_status == "OFAC":
			self.docstatus = 1
		if self.export_or_import == 'Export':
			if self.reference_doctype != 'Sales Invoice':
				frappe.throw('Only Sales Invoice is Allowed for Exports')

			# Allow only Sales Invoices with Sales Taxes marked as export and shipping country outside India.
			ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
			stct_doc = frappe.get_doc("Sales Taxes and Charges Template", ref_doc.taxes_and_charges)
			ship_add_doc = frappe.get_doc("Address", ref_doc.shipping_address_name)
			bill_add_doc = frappe.get_doc("Address", ref_doc.customer_address)
			if ref_doc.docstatus != 1:
				frappe.throw("Only Submitted Documents are Allowed")
			if self.reference_doctype == 'Sales Invoice':
				ship_country = frappe.db.get_value("Address", ref_doc.shipping_address_name, "country")
				if stct_doc.is_export != 1:
					frappe.throw("Only Sales Invoices Marked as Exports are Allowed")
				if ship_country == "India":
					frappe.throw("Only Invoices shipped outside India allowed")

				self.reference_date = ref_doc.posting_date
				self.reference_currency = ref_doc.currency
				self.customer_or_supplier = 'Customer'
				self.customer_or_supplier_name = ref_doc.customer
				self.iec_number = stct_doc.iec_code
				self.bill_to_country = bill_add_doc.country
				self.ship_to_country = ship_add_doc.country
				self.grand_total = ref_doc.grand_total
				self.grand_total_inr = ref_doc.base_grand_total
			
			if self.pan_number:
				validate_pan(self.pan_number)

			if self.shipping_bill_number:
				if self.fob_value == 0:
					frappe.throw(("Enter FOB Value in {0}").format(self.reference_currency))
				else:
					if self.fob_value > self.grand_total:
						frappe.throw(("FOB Value has to be less than {0}").format(self.grand_total))
				if len(str(self.shipping_bill_number)) != 7:
					frappe.throw("Shipping Bill Number is Exactly 7 Digits")
				p = re.compile("[0-9]{7}")
				if not p.match(str(self.shipping_bill_number)):
					frappe.throw("Invalid Shipping Bill Number")
				if not self.shipping_bill_date:
					frappe.throw('Shipping Bill Date is Mandatory for Shipping Bill')
				si_shb = frappe.get_value("Sales Invoice", self.reference_name, "shipping_bill_number")
				if si_shb != self.shipping_bill_number:
					frappe.db.set_value("Sales Invoice", self.reference_name, "shipping_bill_number",
										self.shipping_bill_number)
					frappe.db.set_value("Sales Invoice", self.reference_name, "shipping_bill_date",
										self.shipping_bill_date)

			if self.shipping_bill_date:
				self.submission_date_deadline = add_days(self.shipping_bill_date, 21)
				diff = getdate(self.shipping_bill_date) - getdate(self.reference_date)
				if diff.days > 20 or diff.days < -20:
					frappe.throw('Out of Range Difference, Contact aditya@rigpl.com')

				if self.bank_ifsc_code:
					validate_ifsc_code(self.bank_ifsc_code)
			else:
				self.submission_date_deadline = add_days(self.reference_date, 21)

			if self.brc_number:
				if not self.port_code:
					frappe.throw("Port Code is Mandatory for BRC Number")
				if not self.shipping_bill_number or self.shipping_bill_number == "":
					frappe.throw("Shipping Bill is Mandatory for BRC Number")
				if not self.shipping_bill_date:
					frappe.throw("Shipping Bill Date is Mandatory for BRC Number")
				if not self.brc_date:
					frappe.throw("BRC Date is Mandatory for BRC Number")
				else:
					if add_days(self.brc_date, 1) < add_days(self.shipping_bill_date, 14):
						frappe.throw("BRC Date is NOT VALID")
				if not self.bank_ifsc_code:
					frappe.throw("Bank IFSC is Mandatory for BRC Number")
				if not self.brc_bill_id:
					frappe.throw("BRC Bill ID is mandatory and is different from BRC Number \
						goto DGFT site and enter only IEC Code for Bill ID")
				else:
					if self.brc_bill_id == self.brc_number:
						frappe.throw("BRC Number and Bill ID should be different")
				validate_brc_no(self.brc_number, self.bank_ifsc_code)
				self.brc_status = 'BRC Issued'
				if not self.meis_authorization_no:
					if self.meis_status not in ["MEIS Not Applicable", "MEIS Expired"]:
						self.meis_status = "MEIS Pending"
				else:
					self.meis_status = "MEIS Claimed"
			else:
				if self.brc_status != 'OFAC':
					self.brc_status = 'BRC Pending'
		else:
			frappe.throw("Import Related Tracking Is Not Implemented Yet.")
			if self.reference_doctype != 'Purchase Invoice':
				frappe.throw('Only Purchase Invoice is Allowed for Imports')
			# If IMPORT RELATED TRACKING
			isimport = frappe.db.get_value("Purchase Taxes and Charges Template", ref_doc.taxes_and_charges, "is_import")
			if isimport != 1:
				frappe.throw("Only Purchase Invoices Marked as Import are allowed here")
			self.customer_or_supplier = 'Supplier'
			self.customer_or_supplier_name = ref_doc.supplier
		ship_country = frappe.db.get_value("Address", )

	def import_export_docs_query(reference_document):
		if reference_document == 'Sales Invoice':
			return frappe.db.sql("""SELECT si.name 
				FROM `tabSales Invoice` si, `tabAddress` ad, `tabSales Taxes and Charges Template` stct
				WHERE si.docstatus = 1 AND si.shipping_address_name = ad.name AND 
					si.taxes_and_charges = stct.name AND stct.is_export = 1 """)