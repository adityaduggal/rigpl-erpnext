# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

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
	if filters.get("details") == 1:
		return [
			"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::100", 
			"Email::100", "Status::100", "Requirement:Currency:100", 
			"Territory:Link/Territory:100", "Last Date:Date:100", "Next Date:Date:100",
			"Medium::60", "Last Comm Details::200", "Link Comm:Link/Communication:80", 
			"Comm Owner::120", "Comm Next Contact By::120"
		]
	else:
		return [
			"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::100", 
			"Email::100", "Status::100", "Requirement:Currency:100", 
			"Territory:Link/Territory:100", "Days Since:Int:60",
			"Last Date:Date:100", "Next Date:Date:100",
			"Last Comm Details::200", "Link Comm:Link/Communication:80", 
			"Lead Owner::120", "Next Contact By::120"
		]
	
def get_data(filters):
	conditions = get_conditions(filters)

	if filters.get("status") is None:
		conditions += "AND ld.custom_status != 'Lost' AND ld.status != 'Converted'"

	if filters.get("details") == 1:
		query = """SELECT ld.name, ld.company_name, ld.lead_name, IFNULL(ld.mobile_no,"-"),
			IFNULL(ld.email_id,"-"), ld.custom_status, ld.requirement, IFNULL(ld.territory,"-"),
			co.communication_date, co.next_action_date, co.communication_medium, co.content,
			co.name, co.owner, co.user
			FROM `tabLead` ld, `tabCommunication` co
			WHERE co.communication_type = 'Communication' AND 
				co.reference_doctype = 'Lead' AND co.reference_name = ld.name %s
			ORDER BY ld.name, co.communication_date DESC, co.creation DESC""" %(conditions)
		data = frappe.db.sql(query , as_list=1)
	else:
		query = """SELECT ld.name, ld.company_name, ld.lead_name, IFNULL(ld.mobile_no,"-"),
			IFNULL(ld.email_id,"-"), ld.custom_status, ld.requirement, IFNULL(ld.territory,"-"), 
			IFNULL(ld.lead_owner,"-"), IFNULL(ld.contact_by,"-")
			FROM `tabLead` ld
			WHERE ld.docstatus=0 %s
			ORDER BY ld.name""" %(conditions)

		data = frappe.db.sql(query , as_list=1)
		comm = frappe.db.sql("""SELECT com.name, 
			IFNULL(com.communication_date,'1900-01-01'),
			IFNULL(com.next_action_date,'1900-01-01'),
			IFNULL(com.communication_medium,"-"), com.reference_name, com.content
			FROM `tabCommunication` com
			WHERE com.communication_type = 'Communication' AND
				com.reference_doctype = 'Lead'
			GROUP BY com.reference_name
			ORDER BY com.communication_date DESC""" , as_list=1)
		for i in data:
			if any (i[0] in s for s in comm):
				for j in comm:
					if i[0] == j[4]:
						i.insert(8,'1900-01-01' if j[1] is None else j[1]) #Last communication date
						i.insert(9,'1900-01-01' if j[2] is None else j[2]) #Last communication date
						i.insert(10,"-" if j[5] is None else j[5]) #comm content
						i.insert(11,"-" if j[0] is None else j[0]) #link to the communication
			else:
				i.insert(8,'1900-01-01') #Actual communication date
				i.insert(9,'1900-01-01') #comm medium
				i.insert(10,"-") #comm medium
				i.insert(11,"-") #link to the communication
			i.insert(8, getdate(nowdate())-getdate(i[8]))
	return data


def get_conditions(filters):
	conditions = ""
	if filters.get("details") == 1:
		if filters.get("lead"):
			pass
		else:
			frappe.throw("For Detailed Report Lead Selection is Mandatory")
	if filters.get("lead"):
		conditions += " AND ld.name = '%s'" %filters["lead"]
		
	if filters.get("territory"):
		territory = frappe.get_doc("Territory", filters["territory"])
		if territory.is_group == "Yes" or territory.is_group == 1:
			child_territories = frappe.db.sql("""SELECT name FROM `tabTerritory` 
				WHERE lft >= %s AND rgt <= %s""" %(territory.lft, territory.rgt), as_list = 1)
			for i in child_territories:
				if child_territories[0] == i:
					conditions += " AND (ld.territory = '%s'" %i[0]
					
				elif child_territories[len(child_territories)-1] == i:
					conditions += " OR ld.territory = '%s')" %i[0]
					
				else:
					conditions += " OR ld.territory = '%s'" %i[0]
		else:
			conditions += " AND ld.territory = '%s'" % filters["territory"]

	if filters.get("status"):
		conditions += " AND ld.custom_status = '%s'" % filters["status"]
		
	if filters.get("owner"):
		conditions += " AND ld.lead_owner = '%s'" % filters["owner"]

	if filters.get("next_contact"):
		conditions += " AND ld.contact_by = '%s'" % filters["next_contact"]
			
	return conditions