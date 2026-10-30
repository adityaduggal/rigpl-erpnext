# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from datetime import datetime
from frappe.query_builder.functions import Count, IfNull, Sum
from frappe.utils import add_days, flt, getdate
from ....utils.sales_utils import get_contact_emails, get_contact_phones, get_sales_comms_for_customers, \
	get_sales_comms_for_leads, get_sales_order_totals


def execute(filters=None):
	if not filters: filters = {}
	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data


def get_columns(filters):
	check = 0
	if filters.get("analysis_summary"):
		check += 1
	if filters.get("comm_summary"):
		check += 1
	if filters.get("comm_details"):
		check += 1

	if check == 0:
		frappe.throw("Select One Type of Report by Checking Exactly One Checkbox")
	elif check > 1:
		frappe.throw("Only selecting One Report is Allowed at one time. Check exactly one Checkbox")

	if filters.get("analysis_summary") == 1:
		return [
			"User:Link/User:300", "Type of Communication::200", "# Communication:Int:120",
			"Total Time Spent:Int:120"
		]
	elif filters.get("comm_summary") == 1:
		if not filters.get("document"):
			frappe.throw("Please Select Whether Lead or Customer")
		else:
			if filters.get("document") == 'Lead':
				return [
					"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::150",
					"Email::200", "Status::100", "Requirement:Currency:100",
					"Territory:Link/Territory:100", "Days Since:Int:60", "No of Contacts:Int:50",
					"Last Date:Date:150", "Next Date:Date:150",
					"Last Comm Details::500", "Link Comm:Link/Communication:80",
					"Lead Owner::120", "Next Contact By::120"
				]
			elif filters.get("document") == 'Customer':
				return[
					"Customer:Link/Customer:200", "Territory:Link/Territory:100",
					"Customer Group:Link/Customer Group:100", "Customer Rating:Int:50", "Primary Contact:Link/Contact:200",
					"Mobile::150", "Email::200", "Sales:Currency:200", "Days Since:Int:60", "No of Contact:Int:50",
					"Last Date:Date:150", "Next Date:Date:150", "Last Comm Details::500",
					"Link Comm:Link/Communication:80", "Customer Rep::120"
				]
	elif filters.get("comm_details") == 1:
		if not filters.get("document"):
			frappe.throw("Please Select Whether Lead or Customer")
		elif not filters.get("docname"):
			frappe.throw(f"Please Select the {filters.get('document')} for which Communication Details are needed")
		else:
			if filters.get("document") == "Lead":
				return [
					"Lead:Link/Lead:100", "Company::250", "Contact::250", "Phone #::200",
					"Email::200", "Last Date:Date:150", "Next Date:Date:150",
					"Medium::60", "Last Comm Details::500", "Link Comm:Link/Communication:100",
					"Comm Owner::150"
				]
			elif filters.get("document") == "Customer":
				return [
					"Customer:Link/Customer:250","Contact:Link/Contact:250", "Phone #::200",
					"Email::200", "Last Date:Date:150", "Next Date:Date:150",
					"Medium::60", "Last Comm Details::500", "Link Comm:Link/Communication:100",
					"Comm Owner::150"
				]


def get_data(filters):
	if filters.get("analysis_summary") == 1:
		return get_analysis_summary(filters)
	if filters.get("comm_summary") == 1:
		if filters.get("document") == 'Customer':
			return get_customer_rows(filters, summary=True)
		if filters.get("document") == 'Lead':
			return get_lead_rows(filters, summary=True)
	elif filters.get("comm_details") == 1:
		if filters.get("document") == "Lead":
			return get_lead_rows(filters, summary=False)
		if filters.get("document") == "Customer":
			return get_customer_rows(filters, summary=False)
	return []


def get_analysis_summary(filters):
	dcr = frappe.qb.DocType("Daily Call")
	dcrd = frappe.qb.DocType("Daily Call Details")
	query = (
		frappe.qb.from_(dcr)
		.join(dcrd).on(dcrd.parent == dcr.name)
		.select(dcr.created_by, dcrd.type_of_communication, Count(dcrd.name), Sum(dcrd.duration))
		.where(dcr.docstatus == 1)
		.groupby(dcr.created_by, dcrd.type_of_communication)
	)
	# communication_date is a Datetime, so to_date takes the full day
	if filters.get("from_date"):
		query = query.where(dcrd.communication_date >= getdate(filters["from_date"]))
	if filters.get("to_date"):
		query = query.where(dcrd.communication_date < add_days(getdate(filters["to_date"]), 1))
	if filters.get("document"):
		query = query.where(dcrd.document == filters["document"])
	if filters.get("docname"):
		query = query.where(dcrd.document_name == filters["docname"])
	return query.run(as_list=1)


def join_values(rows, field):
	return "".join(row[field] + " " for row in rows)


def get_customer_rows(filters, summary):
	data = []
	cust_dict = get_customers(filters)
	names = [cust.name for cust in cust_dict]
	contacts = [cust.customer_primary_contact for cust in cust_dict if cust.customer_primary_contact]
	phones, emails = get_contact_phones(contacts), get_contact_emails(contacts)
	if summary:
		so_totals = get_sales_order_totals(names, filters.get("from_date"), filters.get("to_date"))
		comms = get_sales_comms_for_customers(names)
	else:
		comms = get_sales_comms_for_customers(names, filters.get("from_date"), filters.get("to_date"))
	for cust in cust_dict:
		numbers = join_values(phones.get(cust.customer_primary_contact, []), "phone")
		emails_txt = join_values(emails.get(cust.customer_primary_contact, []), "email_id")
		comm_dict = comms.get(cust.name, [])
		if summary:
			row = [cust.name, cust.territory, cust.customer_group, cust.customer_rating,
				   cust.customer_primary_contact, numbers, emails_txt,
				   flt(so_totals.get(cust.name, {}).get("total_net_amt"))]
			data.append(row + get_last_comm(comm_dict, [cust.sales_person]))
		else:
			main_row = [cust.name, cust.customer_primary_contact, numbers, emails_txt]
			data.extend(main_row + get_comm_detail(comm) for comm in comm_dict)
	return data


def get_lead_rows(filters, summary):
	data = []
	lead_dict = get_leads(filters)
	names = [lead.name for lead in lead_dict]
	if summary:
		comms = get_sales_comms_for_leads(names)
	else:
		comms = get_sales_comms_for_leads(names, filters.get("from_date"), filters.get("to_date"))
	for lead in lead_dict:
		comm_dict = comms.get(lead.name, [])
		if summary:
			row = [lead.name, lead.company_name, lead.lead_name, lead.mobile, lead.email, lead.status,
				   lead.requirement, lead.territory]
			data.append(row + get_last_comm(comm_dict, [lead.owner, lead.contact_by]))
		else:
			main_row = [lead.name, lead.company_name, lead.lead_name, lead.mobile, lead.email]
			data.extend(main_row + get_comm_detail(comm) for comm in comm_dict)
	return data


def get_last_comm(comm_dict, owners):
	if not comm_dict:
		return [-1, 0, '1900-01-01', '1900-01-01', "No Communication", ""] + owners
	last = comm_dict[0]
	days_since = (datetime.today() - last.communication_date).days
	return [days_since, last.contacts, last.communication_date, last.next_action_date, last.content,
			last.name] + owners


def get_comm_detail(comm):
	return [comm.communication_date, comm.next_action_date, comm.communication_medium, comm.content,
			comm.name, comm.owner]


def get_customers(filters):
	cu = frappe.qb.DocType("Customer")
	st = frappe.qb.DocType("Sales Team")
	query = (
		frappe.qb.from_(cu)
		.join(st).on(st.parent == cu.name)
		.select(cu.name, cu.territory, cu.customer_group, cu.customer_rating, cu.account_manager,
			cu.customer_primary_contact, st.email_id.as_("sales_person"))
		.where((cu.docstatus == 0) & (st.parenttype == filters.get("document")))
		.orderby(cu.name)
	)
	if filters.get("docname"):
		query = query.where(cu.name == filters["docname"])
	if filters.get("owner"):
		query = query.where(st.email_id == filters["owner"])
	if filters.get("territory"):
		query = query.where(cu.territory == filters["territory"])
	return query.run(as_dict=1)


def get_leads(filters):
	ld = frappe.qb.DocType("Lead")
	query = (
		frappe.qb.from_(ld)
		.select(ld.name, ld.company_name, ld.lead_name, IfNull(ld.mobile_no, "-").as_("mobile"),
			IfNull(ld.email_id, "-").as_("email"), ld.status, ld.requirement,
			IfNull(ld.territory, "-").as_("territory"), IfNull(ld.lead_owner, "-").as_("owner"),
			IfNull(ld.contact_by, "-").as_("contact_by"))
		.where(ld.docstatus == 0)
		.orderby(ld.name)
	)
	if filters.get("docname"):
		query = query.where(ld.name == filters["docname"])
	if filters.get("owner"):
		query = query.where(ld.lead_owner == filters["owner"])
	if filters.get("territory"):
		query = query.where(ld.territory == filters["territory"])
	return query.run(as_dict=1)
