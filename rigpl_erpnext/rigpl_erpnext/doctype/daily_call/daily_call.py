# -*- coding: utf-8 -*-
# Copyright (c) 2018, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from typing import Dict, List

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, now_datetime, get_datetime, time_diff_in_seconds
from ....utils.batch_write_utils import bulk_set_values
from ....utils.follow_up_utils import end_party_follow_ups
from ....utils.rigpl_perm import get_dl_parent
from ....utils.sales_utils import get_link_contacts


class DailyCall(Document):
	def validate(self):
		if not self.call_details:
			frappe.throw("Enter Call Details before creating Communications")
		if not self.created_by:
			frappe.throw("Mandatory Field Created By")
		if not self.next_action_by:
			frappe.throw("Mandatory Field Next Action By")
		leads = get_leads(self.get_party_names("Lead"))
		converted = get_customers_of_leads([name for name, lead in leads.items() if lead.status == "Converted"])
		contacts = {cust: [con.name for con in rows] for cust, rows in
			get_link_contacts("Customer", self.get_party_names("Customer")).items()}
		for row in self.call_details:
			self.validate_row(row, leads, converted, contacts)

	def on_submit(self):
		self.update_lead_statuses()
		comms = {row.name: make_communication(self, row) for row in self.call_details}
		bulk_set_values("Daily Call Details", "communication", comms, {name: None for name in comms})
		for row in self.call_details:
			row.communication = comms[row.name]
		end_party_follow_ups({(row.document, row.document_name) for row in self.call_details},
			exclude=list(comms.values()))
		frappe.msgprint("Created Communications: {}".format(
			", ".join(frappe.get_desk_link("Communication", name) for name in comms.values())))

	def on_cancel(self):
		comms = {row.name: row.communication for row in self.call_details if row.communication}
		# The child rows link the Communications, so clear the links before the delete.
		bulk_set_values("Daily Call Details", "communication", {name: None for name in comms}, comms)
		for name in comms.values():
			# delete_doc also deletes the ToDos of the Communication
			frappe.delete_doc("Communication", name, ignore_permissions=True)
		for row in self.call_details:
			row.communication = None
		if comms:
			frappe.msgprint("Deleted Communications: {}".format(", ".join(comms.values())))

	def get_party_names(self, doctype: str) -> List[str]:
		return list({row.document_name for row in self.call_details if row.document == doctype and row.document_name})

	def validate_row(self, row, leads, converted, contacts):
		if row.communication:
			frappe.throw('Communication {} already exists for Row# {}'.format(
				frappe.get_desk_link('Communication', row.communication), row.idx))
		if not row.document_name:
			frappe.throw("{} is Mandatory in Row# {}".format(row.document or "Document", row.idx))
		if row.document == "Customer":
			row.contact = get_row_contact(row, contacts.get(row.document_name, []))
		elif row.document == "Lead":
			validate_lead_row(row, leads.get(row.document_name), converted)
		else:
			frappe.throw("Document Field is Mandatory in Row# {}".format(row.idx))
		if not row.communication_date:
			frappe.throw("Communication Date is Mandatory in Row# {}".format(row.idx))
		back_dated_days = self.back_dated_days if self.allow_back_dated_entries == 1 else 0
		check_date_time_diff(row.communication_date, days_diff=(-1 * (back_dated_days or 0)),
			type_of_check='date', name_of_field='Communication')
		# A row gets a follow-up only when it has a Next Action Date
		if row.next_action_date:
			check_date_time_diff(row.next_action_date, hours_diff=1, type_of_check='time',
				name_of_field='Next Action')
		row.no_action_required = 0 if row.next_action_date else 1
		if not row.type_of_communication:
			frappe.throw('Type of Communication is Mandatory in Row# {}'.format(row.idx))
		if not row.details:
			frappe.throw('Details of Communication are Mandatory in Row# {}'.format(row.idx))

	def update_lead_statuses(self):
		new_status = {row.document_name: row.lead_status for row in self.call_details
			if row.document == "Lead" and row.lead_status}
		leads = get_leads(list(new_status))
		for name, status in new_status.items():
			if leads[name].status != status:
				# Lead.save runs the Lead hooks, so it stays one save for each changed Lead
				lead = frappe.get_doc("Lead", name)
				lead.status = status
				lead.save()

	def clear_form(self):
		self.call_details = []


def validate_lead_row(row, lead, converted):
	if not lead:
		frappe.throw("Lead {} in Row# {} does not exist".format(row.document_name, row.idx))
	if lead.status == "Converted":
		customer = converted.get(row.document_name)
		if customer:
			frappe.throw(("Selected Lead is already converted to {}. \n"
				"Please select the customer and not this Lead in Row # {}.").format(
				frappe.get_desk_link("Customer", customer), row.idx))
		frappe.throw(("Selected Lead {} in Row# {} is Marked as Converted. \n"
			"Either Change the Lead Status or Link it with a Customer. \n"
			"Since No Customer is Linked to this Lead").format(
			frappe.get_desk_link("Lead", row.document_name), row.idx))
	if not row.lead_status:
		row.lead_status = lead.status
	row.lead_contact_name = lead.lead_name
	row.lead_organisation_name = lead.company_name


def get_row_contact(row, contacts: List[str]) -> str:
	if not contacts:
		frappe.throw('No Contact Found for Customer: {} in Row# {}'.format(row.document_name, row.idx))
	if row.contact:
		if row.contact not in contacts:
			frappe.throw('Selected Contact {} not from Customer:{} in Row# {}'.format(
				row.contact, row.document_name, row.idx))
		return row.contact
	if len(contacts) > 1:
		frappe.throw("Select the Contact for Customer: {} in Row# {}".format(row.document_name, row.idx))
	return contacts[0]


def get_leads(names: List[str]) -> Dict[str, frappe._dict]:
	if not names:
		return {}
	return {lead.name: lead for lead in frappe.get_all("Lead", filters={"name": ["in", names]},
		fields=["name", "status", "lead_name", "company_name"])}


def get_customers_of_leads(leads: List[str]) -> Dict[str, str]:
	"""{lead: customer} for the Leads that a Customer was made from."""
	if not leads:
		return {}
	return {cust.lead_name: cust.name for cust in frappe.get_all("Customer",
		filters={"lead_name": ["in", leads]}, fields=["name", "lead_name"])}


def make_communication(dcr, row) -> str:
	"""Inserts the Communication of a DCR row against its party. Returns its name."""
	comm = frappe.get_doc({
		"doctype": "Communication",
		"communication_type": "Communication",
		"communication_subtype": "Sales Related",
		"communication_medium": row.type_of_communication,
		"communication_date": row.communication_date,
		"duration": row.duration,
		"owner": dcr.created_by,
		"sender": dcr.created_by,
		"user": dcr.next_action_by,
		"reference_doctype": row.document,
		"reference_name": row.document_name,
		"subject": get_call_subject(row),
		"content": row.details,
		"follow_up": 1 if row.next_action_date else 0,
		"next_action_date": row.next_action_date or None,
	})
	if row.contact:
		comm.append("timeline_links", {"link_doctype": "Contact", "link_name": row.contact})
	# The DCR closes the older follow-ups of all its parties at once
	comm.flags.from_daily_call = True
	comm.insert()
	return comm.name


def get_call_subject(row) -> str:
	subject = "Sales Call: {} To:{}:{}".format(row.type_of_communication, row.document, row.document_name)
	if row.document == "Lead":
		return "{} Org:{} Contact:{}".format(subject, row.lead_organisation_name or "", row.lead_contact_name or "")
	return "{} Contact:{}".format(subject, row.contact)


def check_date_time_diff(date_time, type_of_check, name_of_field, days_diff=0, hours_diff=0):
	d = get_datetime(date_time)
	d1 = now_datetime()
	d0 = add_days(d1.date(), days_diff)
	if type_of_check == 'date':
		if d.date() >= d0 and d.date() <= d1.date():
			pass
		else:
			frappe.throw(("{} Date should be between {} and {}").\
				format(name_of_field, str(d0), str(d1.date())))
	else:
		if d.date() < d1.date():
			frappe.throw("{} Date cannot be less than Today's Date".format(name_of_field))
		if d.date() == d1.date():
			if time_diff_in_seconds(d, d1) < (3600*hours_diff):
				frappe.throw("{} Time has to be {} hours after the current time".\
					format(name_of_field, hours_diff))


def check_contact(link_doctype, link_docname, selected_contact=None):
	contact = get_dl_parent(dt="Contact", linked_dt=link_doctype, linked_dn=link_docname)
	if contact:
		if selected_contact:
			check = 0
			for con in contact:
				if selected_contact == con[0]:
					check += 1
			if check == 0:
				frappe.throw('Selected Contact {} not from {}:{}'.\
					format(selected_contact, link_doctype, link_docname))
		else:
			return contact
	else:
		frappe.throw('No Contact Found for {}: {}'.format(link_doctype, link_docname))
