# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
import webnotes
import datetime
from webnotes.utils import flt, getdate, nowdate

def execute(filters=None):

	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data
	
def get_columns(filters):
	if not filters.get("doc_type"):
		webnotes.msgprint("Please select the Type of Follow Up first", raise_exception=1)
		
	if filters.get("doc_type") == "Lead":
		return [
			"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::100","Status::100",
			"Requirement:Currency:100", "Territory::100", "Last Date:Date:80", "Next Date:Date:80", 
			"Medium::100", "Link Comm:Link/Communication:150", "Lead Owner::120", "Next Contact By::120"
		]
	elif filters.get("doc_type") =="Customer":
		return [
			"Customer ID:Link/Customer:150", "Contact::120", "Mobile #::100",
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
			data = webnotes.conn.sql("""SELECT ld.name, ld.company_name, ld.lead_name, ifnull(ld.mobile_no,"-"), 
			ld.custom_status, ld.requirement, ifnull(ld.territory,"-"), ifnull(ld.contact_date,'1900-01-01'), 
			ifnull(ld.lead_owner,"-"), ifnull(ld.contact_by,"-")
			FROM `tabLead` ld
			WHERE ld.docstatus=0 AND ld.custom_status != 'Lost' AND ld.custom_status != 'Converted' %s 
			ORDER BY ld.name""" %conditions_lead , as_list=1)
		else:
			data = webnotes.conn.sql("""SELECT ld.name, ld.company_name, ld.lead_name,ifnull(ld.mobile_no,"-"), 
			ld.custom_status, ld.requirement, ifnull(ld.territory,"-"), ifnull(ld.contact_date,'1900-01-01'), 
			ifnull(ld.lead_owner,"-"), ifnull(ld.contact_by,"-")
			FROM `tabLead` ld
			WHERE ld.docstatus=0 %s 
			ORDER BY ld.name""" %conditions_lead , as_list=1)
		
		comm = webnotes.conn.sql("""SELECT com.name, com.owner, com.parent, com.parenttype,
			ifnull(DATE(com.communication_date),'1900-01-01'), ifnull(com.communication_medium,"-")
			FROM `tabCommunication` com
			WHERE com.parenttype = '%s' 
			GROUP BY com.parent""" %filters["doc_type"], as_list=1)
		
		for i in data:
			if any (i[0] in s for s in comm):
				for j in comm:
					if i[0] == j[2]:
						i.insert(7,'1900-01-01' if j[4] is None else j[4]) #Actual communication date
						i.insert(9,"-" if j[5] is None else j[5]) #comm medium
						i.insert(10,"-" if j[0] is None else j[0]) #link to the communication
			else:
				i.insert(7,'1900-01-01') #Actual communication date
				i.insert(9,"-") #comm medium
				i.insert(10,"-") #link to the communication
	
	
	elif filters.get("doc_type") == "Customer":
		if filters.get("sales_person"):
			data = webnotes.conn.sql("""
				SELECT cu.name, ifnull(cu.customer_rating,"OK") , ifnull(cu.requirement,0), 
				ifnull(cu.territory,"-"), ifnull(cu.next_contact_date,'1900-01-01'), st.sales_person
				FROM `tabCustomer` cu, `tabSales Team` st
				WHERE cu.docstatus =0 AND st.parent = cu.name %s """ %conditions_cust,as_list=1)
					
		else:
			data = webnotes.conn.sql("""
				SELECT cu.name, ifnull(cu.customer_rating,"OK") , ifnull(cu.requirement,0), 
				ifnull(cu.territory,"-"), ifnull(cu.next_contact_date,'1900-01-01')
				FROM `tabCustomer` cu
				WHERE cu.docstatus =0 %s """ %conditions_cust,as_list=1)

		
		con = webnotes.conn.sql("""
			SELECT co.name, co.first_name, co.last_name,
			ifnull(co.mobile_no,"-"), co.customer
			FROM `tabContact` co
			WHERE co.docstatus =0 AND co.customer is not Null
			GROUP BY co.customer""",as_list=1)
		
		for i in data:
			if any (i[0] in s for s in con):
				for j in con:
					if i[0] == j[4]:
						if j[2] is None:
							j[2]=""
						lst = [j[1], " ", j[2]]
						i.insert(1, "-" if j[1] is None else ''.join(lst)) #Add contact name
						i.insert(2, "-" if j[3] is None else j[3]) #Add mobile number
			else:
				i.insert(1, "~No Contact") #Add contact name
				i.insert(2, "~No Contact") #Add contact name
		
		last_so = webnotes.conn.sql("""select so.customer, max(so.transaction_date), so.name
			FROM `tabSales Order` so WHERE so.docstatus = 1 GROUP BY so.customer""", as_list=1)
		
		for i in data:
			if any(i[0] in s for s in last_so):
				for j in last_so:
					if i[0] == j[0]:
						i.insert(4, (datetime.date.today() - getdate(j[1])).days) #insert days
			else:
				i.insert(4,(datetime.date.today() - getdate('1900-01-01')).days)
		
		comm = webnotes.conn.sql("""SELECT com.name, com.owner, com.parent, com.parenttype,
			ifnull(DATE(com.communication_date),'1900-01-01'), ifnull(com.communication_medium,"-")
			FROM `tabCommunication` com
			WHERE com.parenttype = '%s' 
			GROUP BY com.parent""" %filters["doc_type"], as_list=1)
		
		for i in data:
			if any (i[0] in s for s in comm):
				for j in comm:
					if i[0] == j[2]:
						i.insert(7,'1900-01-01' if j[4] is None else j[4]) #Actual communication date
						i.insert(9,"-" if j[5] is None else j[5]) #comm medium
						i.insert(10,"-" if j[0] is None else j[0]) #link to the communication
			else:
				i.insert(7,'1900-01-01') #Actual communication date
				i.insert(9,"-") #comm medium
				i.insert(10,"-") #link to the communication
		
		if filters.get("sales_person") is None:
			salesteam = webnotes.conn.sql("""SELECT st.sales_person, st.parenttype, st.parent
				FROM `tabSales Team` st
				WHERE st.parenttype = 'Customer' %s 
				GROUP BY st.parent""" %conditions_st, as_list=1)
			
			for i in data:
				if any(i[0] in s for s in salesteam):				
					for j in salesteam:
						if i[0] == j[2]:
							i.insert(11, j[0]) #Add Sales Person
				else:
					i.insert(11,"-") #Add sales person if no sales person assigned.
					
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