# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, re
from frappe.model.document import Document
from frappe.utils import getdate, add_days, now_datetime
from rigpl_erpnext.rigpl_erpnext.validations.employee import validate_pan
from rigpl_erpnext.utils import validate_ifsc_code, validate_brc_no

class BRCMEISTracking(Document):
	def validate(self):
		self.validate_fields()

	def validate_fields(self):
		if self.export_or_import == 'Export':
			if self.reference_doctype != 'Sales Invoice':
				frappe.throw('Only Sales Invoice is Allowed for Exports')

			#Allow only Sales Invoices with Sales Taxes marked as export and shipping country outside India.
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
			if self.pan_number:
				validate_pan(self.pan_number)

			if self.shipping_bill_number:
				if len(self.shipping_bill_number) != 7:
					frappe.throw("Shipping Bill Number is Exactly 7 Digits")
				p = re.compile("[0-9]{7}")
				if not p.match(self.shipping_bill_number):
					frappe.throw("Invalid Shipping Bill Number")
				if not self.shipping_bill_date:
					frappe.throw('Shipping Bill Date is Mandatory for Shipping Bill')

			if self.shipping_bill_date:
				diff = getdate(self.shipping_bill_date) - getdate(self.reference_date)
				if diff.days > 10 or diff.days < -10:
					frappe.throw('Out of Range Difference, Contact aditya@rigpl.com')

				if self.bank_ifsc_code:
					validate_ifsc_code(self.bank_ifsc_code)

			if self.brc_number:
				if not self.bank_ifsc_code:
					frappe.throw("Bank IFSC is Mandatory for BRC Number")
				if not self.brc_bill_id:
					frappe.throw("BRC Bill ID is mandatory and is different from BRC Number \
						goto DGFT site and enter only IEC Code for Bill ID")
				else:
					if self.brc_bill_id == self.brc_number:
						frappe.throw("BRC Number and Bill ID should be different")
				validate_brc_no(self.brc_number, self.bank_ifsc_code)
				if self.brc_link[-3:] != 'pdf':
					frappe.throw('Invalid Attachment')
				if self.brc_link[:8] != '/private':
					frappe.throw('Invalid Attachment')
				self.brc_status = 'BRC Issued'
			else:
				self.brc_status = 'BRC Pending'

		else:
			if self.reference_doctype != 'Purchase Invoice':
				frappe.throw('Only Purchase Invoice is Allowed for Imports')
			#If IMPORT RELATED TRACKING
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

