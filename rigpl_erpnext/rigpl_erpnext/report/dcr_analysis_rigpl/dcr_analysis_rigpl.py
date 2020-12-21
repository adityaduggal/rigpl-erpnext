# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from datetime import datetime
from ....utils.sales_utils import get_total_sales_orders, get_sales_comm_for_lead, get_sales_comm_for_cust, \
	get_phone_from_contact, get_email_from_contact
from frappe.utils import flt


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
	cond_dcr, cond_lead, cond_cust = get_conditions(filters)

	if filters.get("analysis_summary") == 1:
		query = """SELECT dcr.created_by, dcrd.type_of_communication, COUNT(dcrd.name),
			SUM(dcrd.duration)
			FROM `tabDaily Call` dcr,  `tabDaily Call Details` dcrd 
			WHERE dcr.docstatus = 1 
			AND dcrd.parent = dcr.name %s 
			GROUP BY dcr.created_by, dcrd.type_of_communication""" % (cond_dcr)
		data = frappe.db.sql(query, as_list=1)
	elif filters.get("comm_summary") == 1:
		if filters.get("document") == 'Customer':
			data = []
			cust_dict = get_customers(filters)
			for cust in cust_dict:
				row = [cust.name, cust.territory, cust.customer_group, cust.customer_rating,
					   cust.customer_primary_contact]
				phone_dict = get_phone_from_contact(cust.customer_primary_contact)
				numbers = ""
				if phone_dict:
					for mob in phone_dict:
						numbers += mob.phone + " "
				emails = ""
				email_dict = get_email_from_contact(cust.customer_primary_contact)
				if email_dict:
					for email in email_dict:
						emails += email.email_id + " "
				total_so = get_total_sales_orders(cust.name, filters.get("from_date"), filters.get("to_date"))
				row += [numbers, emails, flt(total_so[0].total_net_amt)]
				comm_dict = get_sales_comm_for_cust(cust.name)
				if comm_dict:
					days_since = (datetime.today() - comm_dict[0].communication_date).days
					row += [days_since, comm_dict[0].contacts, comm_dict[0].communication_date,
							comm_dict[0].next_action_date, comm_dict[0].content, comm_dict[0].name, cust.sales_person]
				else:
					row += [-1, 0, '1900-01-01', '1900-01-01', "No Communication", "", cust.sales_person]
				data.append(row)

		elif filters.get("document") == 'Lead':
			data = []
			lead_dict = get_leads(filters)
			for lead in lead_dict:
				row = [lead.name, lead.company_name, lead.lead_name, lead.mobile, lead.email, lead.status,
					   lead.requirement, lead.territory]
				comm_dict = get_sales_comm_for_lead(lead.name)
				if comm_dict:
					days_since = (datetime.today() - comm_dict[0].communication_date).days
					row += [days_since, comm_dict[0].contacts, comm_dict[0].communication_date,
							comm_dict[0].next_action_date, comm_dict[0].content, comm_dict[0].name, lead.owner,
							lead.contact_by]
				else:
					row += [-1, 0, '1900-01-01', '1900-01-01', "No Communication", "", lead.owner, lead.contact_by]
				data.append(row)
	elif filters.get("comm_details") == 1:
		data = []
		if filters.get("document") == "Lead":
			lead_dict = get_leads(filters)
			for lead in lead_dict:
				main_row = [lead.name, lead.company_name, lead.lead_name, lead.mobile, lead.email]
				comm_dict = get_sales_comm_for_lead(lead_name=lead.name, frm_date=filters.get("from_date"),
													to_date=filters.get("to_date"))
				if comm_dict:
					for comm in comm_dict:
						rowcomm = [comm.communication_date, comm.next_action_date, comm.communication_medium,
								comm.content, comm.name, comm.owner]
						new_row = main_row + rowcomm
						data.append(new_row)
		elif filters.get("document") == "Customer":
			cust_dict = get_customers(filters)
			for cust in cust_dict:
				main_row = [cust.name, cust.customer_primary_contact]
				phone_dict = get_phone_from_contact(cust.customer_primary_contact)
				numbers = ""
				if phone_dict:
					for mob in phone_dict:
						numbers += mob.phone + " "
				emails = ""
				email_dict = get_email_from_contact(cust.customer_primary_contact)
				if email_dict:
					for email in email_dict:
						emails += email.email_id + " "
				main_row += [numbers, emails]
				comm_dict = get_sales_comm_for_cust(cust_name=cust.name, frm_date=filters.get("from_date"),
													to_date=filters.get("to_date"))
				if comm_dict:
					for comm in comm_dict:
						rowcomm = [comm.communication_date, comm.next_action_date, comm.communication_medium,
								comm.content, comm.name, comm.owner]
						new_row = main_row + rowcomm
						data.append(new_row)
	return data


def get_customers(filters):
	cond_cust = get_conditions(filters)[2]
	cust_query = """SELECT cu.name, cu.territory, cu.customer_group, cu.customer_rating, cu.account_manager, 
	cu.customer_primary_contact, st.email_id as sales_person
	FROM `tabCustomer` cu, `tabSales Team` st 
	WHERE cu.docstatus = 0 AND st.parenttype = '%s' AND st.parent = cu.name %s 
	ORDER BY cu.name""" % (filters.get('document'), cond_cust)
	cust_dict = frappe.db.sql(cust_query, as_dict=1)
	return cust_dict

def get_leads(filters):
	cond_lead = get_conditions(filters)[1]
	ld_query = """SELECT ld.name, ld.company_name, ld.lead_name, IFNULL(ld.mobile_no,"-") as mobile,
	IFNULL(ld.email_id,"-") as email, ld.status, ld.requirement, IFNULL(ld.territory,"-") as territory, 
	IFNULL(ld.lead_owner,"-") as owner, IFNULL(ld.contact_by,"-") as contact_by
	FROM `tabLead` ld WHERE ld.docstatus=0 %s ORDER BY ld.name""" % (cond_lead)
	lead_dict = frappe.db.sql(ld_query, as_dict=1)
	return lead_dict


def get_conditions(filters):
	cond_dcr = ""
	cond_lead = ""
	cond_cust = ""

	if filters.get("from_date"):
		cond_dcr += " AND dcrd.communication_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		cond_dcr += " AND dcrd.communication_date <= '%s'" % filters["to_date"]

	if filters.get("document"):
		cond_dcr += " AND dcrd.document = '%s'" % filters["document"]

	if filters.get("docname"):
		cond_dcr += " AND dcrd.document = '%s' AND dcrd.document_name = '%s'" % (filters["document"],
																				 filters["docname"])
		if filters.get("document") == 'Lead':
			cond_lead += " AND ld.name = '%s'" % filters["docname"]
		elif filters.get("document") == 'Customer':
			cond_cust += " AND cu.name = '%s'" % filters["docname"]

	if filters.get("owner"):
		if filters.get("document") == "Lead":
			cond_lead += " AND ld.lead_owner = '%s'" % filters["owner"]
		elif filters.get("document") == "Customer":
			cond_cust += " AND st.email_id = '%s' " % filters["owner"]

	if filters.get("territory"):
		if filters.get("document") == "Lead":
			cond_lead += " AND ld.territory = '%s'" % filters["territory"]
		elif filters.get("document") == "Customer":
			cond_cust += " AND "

	return cond_dcr, cond_lead, cond_cust
