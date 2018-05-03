# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = {}
	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data

def get_columns(filters):
	check = 0
	if filters.get("analysis_summary"):
		check += 1
	if filters.get("analysis_details"):
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
	elif filters.get("analysis_details") == 1:
		return [
		]
	elif filters.get("comm_summary") == 1:
		if not filters.get("document"):
			frappe.throw("Please Select Whether Lead or Customer")
		else:
			if filters.get("document") == 'Lead':
				return [
					"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::100", 
					"Email::100", "Status::100", "Requirement:Currency:100", 
					"Territory:Link/Territory:100", "Days Since:Int:60",
					"Last Date:Date:100", "Next Date:Date:100",
					"Last Comm Details::200", "Link Comm:Link/Communication:80", 
					"Lead Owner::120", "Next Contact By::120"
				]
	elif filters.get("comm_details") == 1:
		if not filters.get("document"):
			frappe.throw("Please Select Whether Lead or Customer")
		elif not filters.get("document_name"):
			frappe.throw("Please Select the {} for which Communication Details are needed").format(filters.get("document"))
		else:
			return [
				"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::100", 
				"Email::100", "Status::100", "Requirement:Currency:100", 
				"Territory:Link/Territory:100", "Last Date:Date:100", "Next Date:Date:100",
				"Medium::60", "Last Comm Details::200", "Link Comm:Link/Communication:80", 
				"Comm Owner::120", "Comm Next Contact By::120"
			]
def get_data(filters):
	cond_dcr, cond_lead = get_conditions(filters)

	if filters.get("analysis_summary") == 1:
		query = """SELECT dcr.created_by, dcrd.type_of_communication, COUNT(dcrd.name),
			SUM(dcrd.duration)
			FROM `tabDaily Call` dcr,  `tabDaily Call Details` dcrd 
			WHERE dcr.docstatus = 1 
			AND dcrd.parent = dcr.name %s 
			GROUP BY dcr.created_by, dcrd.type_of_communication""" %(cond_dcr)
	elif filters.get("analysis_details") == 1:
		frappe.throw("WIP")
	elif filters.get("comm_summary") == 1:
		if filters.get("document") == 'Customer':
			pass
		elif filters.get("document") == 'Lead':
			query = """SELECT ld.name, ld.company_name, ld.lead_name, IFNULL(ld.mobile_no,"-"),
			IFNULL(ld.email_id,"-"), ld.status, ld.requirement, IFNULL(ld.territory,"-"), "-",
			"X", "X", "X", comm.name, IFNULL(ld.lead_owner,"-"), IFNULL(ld.contact_by,"-")
			FROM `tabLead` ld, `tabCommunication` comm
			WHERE ld.docstatus=0 AND ld.name = comm.timeline_name %s
			ORDER BY ld.name""" %(cond_lead)
	elif filters.get("comm_details") == 1:
		frappe.throw("WIP")
	#frappe.msgprint(query)
	data = frappe.db.sql(query, as_list=1)
	return data

def get_conditions(filters):
	cond_dcr = ""
	cond_lead = ""
	if filters.get("from_date"):
		cond_dcr += " AND dcrd.communication_date >= '%s'" %filters["from_date"]

	if filters.get("to_date"):
		cond_dcr += " AND dcrd.communication_date <= '%s'" %filters["to_date"]

	if filters.get("document"):
		cond_dcr += " AND dcrd.document <= '%s'" %filters["document"]

	if filters.get("document") == 'Lead':
		if filters.get("document_name"):
			cond_lead += " AND ld.name = '%s'" %filters["document_name"]
	
	return cond_dcr, cond_lead