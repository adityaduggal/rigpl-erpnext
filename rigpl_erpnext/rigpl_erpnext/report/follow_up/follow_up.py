from __future__ import unicode_literals
import frappe
import datetime
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):

	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data

def get_columns(filters):
	if not filters.get("doc_type"):
		frappe.msgprint("Please select the Type of Follow Up first", raise_exception=1)

	if filters.get("doc_type") == "Lead":
		return [
			"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::100","Email::100", "Status::100",
			"Requirement:Currency:100", "Territory::100", "Last Date:Date:80", "Next Date:Date:80",
			"Medium::100", "Link Comm:Link/Communication:150", "Lead Owner::120", "Next Contact By::120"
		]
	elif filters.get("doc_type") =="Customer":
		return [
			"Customer ID:Link/Customer:150", "Contact::120", "Mobile #::100", "Email::100",
			"Status::100", "Days Since SO:Int:50", "Requirement:Currency:100", "Territory::100",
			"Last Date:Date:80", "Next Date:Date:80", "Medium::100",
			"Link Comm:Link/Communication:120","Sales Person:Link/Sales Person:120"
		]
def get_data(filters):
	conditions_cust = get_conditions_cust(filters)
	conditions_lead = get_conditions_lead(filters)
	conditions_st = get_conditions_st(filters)

	if filters.get("doc_type") == "Lead":
		if filters.get("status") is None:
			data = frappe.db.sql("""SELECT ld.name, ld.company_name, ld.lead_name, ifnull(ld.mobile_no,"-"),
			ifnull(ld.email_id,"-"), ld.custom_status, ld.requirement, ifnull(ld.territory,"-"),
			ifnull(ld.contact_date,'1900-01-01'), ifnull(ld.lead_owner,"-"), ifnull(ld.contact_by,"-")
			FROM `tabLead` ld
			WHERE ld.docstatus=0 AND ld.custom_status != 'Lost' AND ld.custom_status != 'Converted' %s
			ORDER BY ld.name""" %conditions_lead , as_list=1)
		else:
			data = frappe.db.sql("""SELECT ld.name, ld.company_name, ld.lead_name,ifnull(ld.mobile_no,"-"),
			ld.custom_status, ld.requirement, ifnull(ld.territory,"-"), ifnull(ld.contact_date,'1900-01-01'),
			ifnull(ld.lead_owner,"-"), ifnull(ld.contact_by,"-")
			FROM `tabLead` ld
			WHERE ld.docstatus=0 %s
			ORDER BY ld.name""" %conditions_lead , as_list=1)

		comm = frappe.db.sql("""SELECT com.name, com.owner, com.parent, com.parenttype,
			ifnull(MAX(DATE(com.communication_date)),'1900-01-01'), ifnull(com.communication_medium,"-")
			FROM `tabCommunication` com
			WHERE com.parenttype = '%s'
			GROUP BY com.parent""" %filters["doc_type"], as_list=1)

		for i in data:
			if any (i[0] in s for s in comm):
				for j in comm:
					if i[0] == j[2]:
						i.insert(8,'1900-01-01' if j[4] is None else j[4]) #Actual communication date
						i.insert(10,"-" if j[5] is None else j[5]) #comm medium
						i.insert(11,"-" if j[0] is None else j[0]) #link to the communication
			else:
				i.insert(8,'1900-01-01') #Actual communication date
				i.insert(10,"-") #comm medium
				i.insert(11,"-") #link to the communication


	elif filters.get("doc_type") == "Customer":
		if filters.get("sales_person"):
			data = frappe.db.sql("""
				SELECT cu.name, ifnull(cu.customer_rating,"OK") , ifnull(cu.requirement,0),
				ifnull(cu.territory,"-"), ifnull(cu.next_contact_date,'1900-01-01'), st.sales_person
				FROM `tabCustomer` cu, `tabSales Team` st
				WHERE cu.docstatus =0 AND st.parent = cu.name %s """ %conditions_cust,as_list=1)

		else:
			data = frappe.db.sql("""
				SELECT cu.name, ifnull(cu.customer_rating,"OK") , ifnull(cu.requirement,0),
				ifnull(cu.territory,"-"), ifnull(cu.next_contact_date,'1900-01-01')
				FROM `tabCustomer` cu
				WHERE cu.docstatus =0 %s """ %conditions_cust,as_list=1)


		con = frappe.db.sql("""
			SELECT co.name, co.first_name, co.last_name,
			ifnull(co.mobile_no,"-"), ifnull(co.email_id,"-"), co.customer
			FROM `tabContact` co
			WHERE co.docstatus =0 AND co.customer is not Null
			GROUP BY co.customer""",as_list=1)

		for i in data:
			if any (i[0] in s for s in con):
				for j in con:
					if i[0] == j[5]:
						if j[2] is None:
							j[2]=""
						lst = [j[1], " ", j[2]]
						i.insert(1, "-" if j[1] is None else ''.join(lst)) #Add contact name
						i.insert(2, "-" if j[3] is None else j[3]) #Add mobile number
						i.insert(3, "-" if j[4] is None else j[4]) #Add email id
			else:
				i.insert(1, "~No Contact") #Add contact name
				i.insert(2, "~No Contact") #Add mobile #
				i.insert(3, "~No Contact") #Add email id

		last_so = frappe.db.sql("""select so.customer, max(so.transaction_date), so.name
			FROM `tabSales Order` so WHERE so.docstatus = 1 GROUP BY so.customer""", as_list=1)

		for i in data:
			if any(i[0] in s for s in last_so):
				for j in last_so:
					if i[0] == j[0]:
						i.insert(5, (datetime.date.today() - getdate(j[1])).days) #insert days
			else:
				i.insert(5,(datetime.date.today() - getdate('1900-01-01')).days)

		comm = frappe.db.sql("""SELECT com.name, com.owner, com.parent, com.parenttype,
			ifnull(MAX(DATE(com.communication_date)),'1900-01-01'), ifnull(com.communication_medium,"-")
			FROM `tabCommunication` com
			WHERE com.parenttype = '%s'
			GROUP BY com.parent""" %filters["doc_type"], as_list=1)

		for i in data:
			if any (i[0] in s for s in comm):
				for j in comm:
					if i[0] == j[2]:
						i.insert(8,'1900-01-01' if j[4] is None else j[4]) #Actual communication date
						i.insert(10,"-" if j[5] is None else j[5]) #comm medium
						i.insert(11,"-" if j[0] is None else j[0]) #link to the communication
			else:
				i.insert(8,'1900-01-01') #Actual communication date
				i.insert(10,"-") #comm medium
				i.insert(11,"-") #link to the communication

		if filters.get("sales_person") is None:
			salesteam = frappe.db.sql("""SELECT st.sales_person, st.parenttype, st.parent
				FROM `tabSales Team` st
				WHERE st.parenttype = 'Customer' %s
				GROUP BY st.parent""" %conditions_st, as_list=1)

			for i in data:
				if any(i[0] in s for s in salesteam):
					for j in salesteam:
						if i[0] == j[2]:
							i.insert(12, j[0]) #Add Sales Person
				else:
					i.insert(12,"-") #Add sales person if no sales person assigned.

	return data


def get_conditions_cust(filters):
	conditions_cust = ""

	if filters.get("territory"):
		conditions_cust += " and cu.territory = '%s'" % filters["territory"]

	if filters.get("sales_person"):
		conditions_cust += " and st.sales_person = '%s'" % filters["sales_person"]

	if filters.get("status"):
		conditions_cust += " AND cu.customer_rating = '%s'" % filters["status"]

	return conditions_cust

def get_conditions_lead(filters):
	conditions_lead = ""

	if filters.get("owner"):
		conditions_lead += " AND ld.lead_owner = '%s'" % filters["owner"]

	if filters.get("next_contact"):
		conditions_lead += " AND ld.contact_by = '%s'" % filters["next_contact"]

	if filters.get("status"):
		conditions_lead += " AND ld.custom_status = '%s'" % filters["status"]

	return conditions_lead

def get_conditions_st(filters):
	conditions_st = ""

	if filters.get("sales_person"):
		conditions_st += " AND st.sales_person = '%s'" % filters["sales_person"]

	return conditions_st
