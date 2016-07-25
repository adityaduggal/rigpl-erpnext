# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from datetime import datetime, date, timedelta
from frappe.utils import getdate, add_days, now_datetime, nowtime, get_datetime, time_diff_in_seconds

class SalesCallTool(Document):
	#TODO: Move Many of the COmmunications' Validatoins to Comm
	def create_communication(self):
		self.validate()
		self.update_lead()
		comm = frappe.new_doc("Communication")
		comm.owner = self.created_by
		comm.user = self.next_action_by
		comm.communication_date = self.date_of_communication
		#add custom field for next_action_date in Communication
		#add custom field for communication_subtype in Communication
		if self.no_action_required <> 1:
			comm.follow_up = 1
		comm.next_action_date = self.next_action_date #This would add a TODO to USER fields' account on that day
		comm.communication_subtype = "Sales Related"
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
		self.clear_form()
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
			elif self.document == "Lead":
				if self.customer or self.contact:
					frappe.throw("Contact and Customer not allowed for Lead Communication")
				#Check if Lead is converted
				if self.lead:
					lead = frappe.get_doc("Lead", self.lead)
					self.lead_contact_name = lead.lead_name
					self.lead_organisation_name = lead.company_name
					if lead.status == "Converted":
						customer = frappe.db.sql("""SELECT name FROM `tabCustomer` 
							WHERE lead_name = '%s'""" %(self.lead), as_list=1)
						frappe.throw(("Selected Lead is already converted to {0}. \n\
							Please select the customer and not this Lead.").format(customer[0][0]))
				else:
					frappe.throw("Lead Mandatory")
			if self.date_of_communication:
				d = get_datetime(self.date_of_communication)
				d1 = now_datetime()
				d0 = add_days(d1, -5)
				if d.date() >= d0.date() and d.date() <= d1.date():
					pass
				else:
					frappe.throw(("Communication Date should be between {0} and {1}").format(d0.date(),d1.date()))
			else:
				frappe.throw("Date of Communication is Mandatory")
			if self.next_action_date:
				d2 = get_datetime(self.next_action_date)
				if d2.date() < d1.date():
					frappe.throw("Next Action Date cannot be less than Today's Date")
				if d2.date() == d1.date():
					if time_diff_in_seconds(d2, d1) < 3600:
						frappe.throw("Next Action Time has to be 1 hour after the current time")
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
			#Check only System Managers can do this Entry
			user = frappe.session.user
			roles = frappe.db.sql("""SELECT role from `tabUserRole` where parent = '%s' """ \
				%user, as_list=1)
			self.next_action_date = ""
		else:
			if not self.next_action_date:
				frappe.throw("Please add a Next Action Date")
			
	def clear_form(self):
		self.document = ""
		self.lead = ""
		self.customer = ""
		
	def update_lead(self):
		if self.document == "Lead":
			frappe.db.set_value("Lead", self.lead, "custom_status", self.status_of_lead)
