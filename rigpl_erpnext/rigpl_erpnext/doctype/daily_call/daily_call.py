# -*- coding: utf-8 -*-
# Copyright (c) 2018, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from datetime import datetime, date, timedelta
from frappe.utils import getdate, add_days, now_datetime, nowtime, get_datetime, time_diff_in_seconds

class DailyCall(Document):
	#TODO: Move Many of the COmmunications' Validatoins to Comm
	def on_submit(self):
		self.create_communications()

	def on_cancel(self):
		self.delete_communications()

	def delete_communications(self):
		for row in self.call_details:
			if row.communication is not None:
				del_comm =  frappe.get_doc("Communication", row.communication)
				del_comm.flags.ignore_permissions = True
				del_comm.delete()
				frappe.msgprint('Deleted Communication: {}'.format(row.communication))
				frappe.db.set_value('Daily Call Details', row.name, 'communication', None)
				row.communication = ''

	def create_communications(self):
		self.validate()
		for row in self.call_details:
			create_new_communication(self.created_by, self.next_action_by, row)

	def validate(self):
		if self.call_details:
			for row in self.call_details:
				if row.communication:
					frappe.throw('Communication {} already exists for Row# {}'.\
						format(frappe.get_desk_link('Communication', row.communication), row.idx))
				if row.document == "Customer":
					if row.document_name:
						if row.contact:
							check_contact(row.document, row.document_name, row.contact)
						else:
							row.contact = check_contact(row.document, row.document_name, row.contact)[0][0]
					else:
						frappe.throw("Customer is Mandatory")
				elif row.document == "Lead":
					#Check if Lead is converted
					if row.document_name:
						lead = frappe.get_doc("Lead", row.document_name)
						row.lead_status = lead.status
						row.lead_contact_name = lead.lead_name
						row.lead_organisation_name = lead.company_name
						if lead.status == "Converted":
							customer = frappe.db.sql("""SELECT name FROM `tabCustomer` 
								WHERE lead_name = '%s'""" %(self.lead), as_list=1)
							frappe.throw(("Selected Lead is already converted to {0}. \n\
								Please select the customer and not this Lead.").format(customer[0][0]))

					update_lead_status(lead, row.lead_status)
				else:
					frappe.throw("Document Field is Mandatory")
				if row.communication_date:
					d = get_datetime(row.communication_date)
					d1 = now_datetime()
					d0 = add_days(d1, -5)
					if d.date() >= d0.date() and d.date() <= d1.date():
						pass
					else:
						frappe.throw(("Communication Date should be between {0} and {1}").format(d0.date(),d1.date()))
				else:
					frappe.throw("Communication Date is Mandatory")
				if row.next_action_date:
					d2 = get_datetime(row.next_action_date)
					if d2.date() < d1.date():
						frappe.throw("Next Action Date cannot be less than Today's Date")
					if d2.date() == d1.date():
						if time_diff_in_seconds(d2, d1) < 3600:
							frappe.throw("Next Action Time has to be 1 hour after the current time")
				if not row.type_of_communication:
					frappe.throw('Type of Communication is Mandatory')
				if not row.details:
					frappe.throw('Details of Communication are Mandatory')
			
			if row.no_action_required == 1:
				#Check only System Managers can do this Entry
				user = frappe.session.user
				roles = frappe.db.sql("""SELECT role from `tabUserRole` where parent = '%s' """ \
					%user, as_list=1)
				row.next_action_date = ""
			else:
				if not row.next_action_date:
					frappe.throw("Please add a Next Action Date")
		else:
			frappe.throw("Enter Call Details before creating Communications")
		
		if self.created_by:
			pass
		else:
			frappe.throw("Mandatory Field Created By")
		
		if self.next_action_by:
			pass
		else:
			frappe.throw("Mandatory Field Next Action By")
			
	def clear_form(self):
		self.call_details = []
		
def update_lead_status(lead_doc, new_status):
	if lead_doc.status != new_status:
		lead_doc.status = new_status
		lead_doc.save()
		#frappe.db.set_value("Lead", self.lead, "custom_status", self.lead_status)

@frappe.whitelist()
def get_linked_contact(doctype, txt, searchfield, start, page_len, filters, link_doctype, link_docname):
	frappe.throw("STOP")
	return frappe.db.sql("""SELECT name, link_name FROM `tabDynamic Link`
		WHERE parenttype = "Contact" AND link_doctype = '%s' AND link_name = '%s'
			AND ({key} LIKE %(txt)s
				OR parent LIKE %(txt)s)
			{mcond}
		ORDER BY
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, parent), locate(%(_txt)s, parent), 99999),
			parent
		LIMIT %(link_doctype, link_docname), %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})

def check_contact(link_doctype, link_docname, selected_contact=None):
	contact = frappe.db.sql(""" SELECT parent FROM `tabDynamic Link` 
		WHERE parenttype = 'Contact' AND link_doctype = '%s' 
		AND link_name = '%s'"""%(link_doctype, link_docname), as_list=1)
	if contact:
		if selected_contact:
			if selected_contact in contact[0]:
				pass
			else:
				frappe.throw('Selected Contact {} not from {}:{}'.\
					format(selected_contact, link_doctype, link_docname))
		else:
			return contact
	else:
		frappe.throw('No Contact Found for {}: {}'.format(link_doctype, link_docname))

def create_new_communication(created_by, next_action_by, row):
	comm = frappe.new_doc("Communication")
	comm.owner = created_by
	comm.user = next_action_by
	comm.communication_date = row.communication_date
	comm.duration = row.duration
	#add custom field for next_action_date in Communication
	#add custom field for communication_subtype in Communication
	if row.no_action_required != 1:
		comm.follow_up = 1
	comm.next_action_date = row.next_action_date #This would add a TODO to USER fields' account on that day
	comm.communication_subtype = "Sales Related"
	comm.communication_medium = row.type_of_communication 
	#Change the above Select field by customize form view in Communication
	comm.communication_type = "Communication"
	comm.content = row.details
	if row.document == "Customer":
		comm.reference_doctype = "Contact"
		comm.reference_name = row.contact
		comm.timeline_doctype = row.document
		comm.timeline_name = row.document_name
		comm.subject = "Sales Call: " + row.type_of_communication + " To:" + \
			row.document + ":" + row.document_name + " Contact:" + row.contact
	elif row.document == "Lead":
		comm.reference_doctype = row.document
		comm.reference_name = row.document_name
		comm.subject = "Sales Call: " + row.type_of_communication + " To:" + \
			row.document + ":" + row.document_name + " Org:" +  \
			row.lead_organisation_name + " Contact:" + row.lead_contact_name
	else:
		frappe.throw("Error Contact aditya@rigpl.com")
	comm.insert()
	frappe.db.set_value('Daily Call Details', row.name, 'communication', comm.name)
	row.communication = comm.name
	frappe.msgprint("Created New Communication {}".format(frappe.get_desk_link('Communication', comm.name)))