# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from datetime import datetime, date, timedelta
from frappe.utils import getdate, add_days, nowdate

class SalesCallTool(Document):
	def create_communication(self):
		self.validate()
		comm = frappe.new_doc("Communication")
		comm.owner = self.created_by
		comm.user = self.next_action_by
		comm.communication_date = self.date_of_communication
		#add custom field for next_action_date in Communication
		#add custom field for communication_subtype in Communication
		#comm.next_action_date = self.next_action_date #This would add a TODO to USER fields' account on that day
		#comm.communication_subtype = "Sales Related"
		comm.communication_medium = self.type_of_communication 
		#Change the above Select field by customize form view in Communication
		comm.communication_type = "Communication"
		comm.content = self.details
		if self.document == "Customer":
			comm.reference_doctype = "Contact"
			comm.reference_name = self.contact
			comm.timeline_doctype = "Customer"
			comm.timeline_name = self.customer
			comm.subject = "Sales Call: " + self.type_of_communication + " To:" + \
				self.customer + " Contact:" + self.contact
		elif self.document == "Lead":
			comm.reference_doctype = "Lead"
			comm.reference_name = self.lead
			comm.subject = "Sales Call: " + self.type_of_communication + " To:" + \
				self.lead + " Org:" + self.lead_organisation_name + " Contact:" + self.lead_contact_name
		else:
			frappe.throw("Error Contact aditya@rigpl.com")
		comm.insert()
		#self.clear_form()
		frappe.msgprint("Created New Communication")

	def validate(self):
		if self.document:
			if self.document == "Customer":
				if self.customer:
					if self.contact:
						contact = frappe.get_doc("Contact", self.contact)
						if contact.customer <> self.customer:
							frappe.throw("Contact selected should be linked to the Customer")
					else:
						frappe.throw("Contact is Mandatory")
				else:
					frappe.throw("Customer is Mandatory")
				if self.lead:
					frappe.throw("Lead for Customer Communication is not allowed")
			if self.document == "Lead":
				if self.customer or self.contact:
					frappe.throw("Contact and Customer not allowed for Lead Communication")
			if self.date_of_communication:
				d = getdate(self.date_of_communication)
				d0 = add_days(d, -5)
				d1 = getdate(nowdate())
				if d >= d0 and d <= d1:
					pass
				else:
					frappe.throw("Communication Date should be Today or T-5 days only")
			if self.next_action_date:
				d2 = getdate(self.next_action_date)
				if d2 < d1:
					frappe.throw("Next Action Date Cannot be Less than Communication Date")
		else:
			frappe.throw("Select Document before creating a Communication")
		
		if self.created_by:
			pass
		else:
			frappe.throw("Mandatory Field Created By")
		
		if self.next_action_by:
			pass
		else:
			frappe.throw("Mandatory Field Next Action By")
			
		if self.no_action_required == 1:
			self.next_action_date = ""
			
	def clear_form(self):
		self.document = ""
