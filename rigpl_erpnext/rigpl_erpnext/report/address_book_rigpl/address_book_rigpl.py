# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	conditions = get_conditions (filters)
	data = get_entries(filters, conditions)

	return columns, data
	
def get_columns(filters):

	columns = [
		"Customer:Link/Customer:150", "Customer Name::150", "Customer Type::80", 
		"Customer Group:Link/Customer Group:150",
		"Territory:Link/Territory:80" 
		]
		
	columns_address = ["Address Link:Link/Address:150", "Address Type::50", 
		"Address Line1::150", "Address Line2::150", "City::100", "State::100", 
		"Postal Code::80", "Country::100", "Email::100", "Phone::150", "Fax::100", "GSTIN::130"]
		
	columns_contact = ["Contact Link:Link/Contact:100", "First Name::100", "Last Name::100",
		"Email::200", "Phone::150", "Mobile::100", "Department::100", "Designation::100", 
		"Notes::200", "Userid::150", "Birthday:Date:80", "Anniversary:Date:80"]
		
	if filters.get("type") == "Only Addresses":
		columns = columns + columns_address
			
	elif filters.get("type") == "Only Contacts":
			columns = columns + columns_contact
	
	else:
		columns = columns + columns_address + columns_contact
	
	return columns
		
def get_entries(filters, conditions):
	data = []
	if filters.get("type") == "Only Addresses":
		query = """SELECT cu.name,  cu.customer_name, cu.customer_type, cu.customer_group,
			cu.territory, ad.name, ad.address_type, ad.address_line1, ad.address_line2,
			ad.city, ad.state, ad.pincode, ad.country, ad.email_id, ad.phone, ad.fax, ad.gstin,
			ad.excise_no, ad.service_tax_no
			FROM `tabCustomer` cu, `tabAddress` ad, `tabDynamic Link` dl
			WHERE
				dl.link_doctype = 'Customer' AND
				dl.link_name = cu.name AND
				dl.parenttype = 'Address' AND
				dl.parent = ad.name %s""" % conditions
			
		data = frappe.db.sql(query, as_list=1)
		
	elif filters.get("type") == "Only Contacts":
		query = """SELECT cu.name,  cu.customer_name, cu.customer_type, cu.customer_group,
			cu.territory, con.name, con.first_name, con.last_name, con.email_id, con.phone,
			con.mobile_no, con.department, con.designation, con.notes, con.user, con.birthday,
			con.anniversary
			FROM `tabCustomer` cu, `tabContact` con, `tabDynamic Link` dl
			WHERE
				dl.link_doctype = 'Customer' AND
				dl.link_name = cu.name AND
				dl.parenttype = 'Contact' AND
				dl.parent = con.name %s""" % conditions
			
		data = frappe.db.sql(query, as_list=1)
		
	return data

def get_conditions(filters):
	cond = ""
	if filters.get("customer"):
		cond += "AND cu.name = '%s'" %(filters["customer"])
		
	if filters.get("customer_type"):
		cond += "AND cu.customer_type = '%s'" %(filters["customer_type"])	
		
	if filters.get("territory"):
		territory = frappe.get_doc("Territory", filters["territory"])
		if territory.is_group == 1:
			child_territories = frappe.db.sql("""SELECT name FROM `tabTerritory` 
				WHERE lft >= %s AND rgt <= %s""" %(territory.lft, territory.rgt), as_list = 1)
			for i in child_territories:
				if child_territories[0] == i:
					cond += " AND (cu.territory = '%s'" %i[0]
				elif child_territories[len(child_territories)-1] == i:
					cond += " OR cu.territory = '%s')" %i[0]
				else:
					cond += " OR cu.territory = '%s'" %i[0]
		else:
			cond += " AND cu.territory = '%s'" % filters["territory"]
			
	if filters.get("customer_group"):
		cg = frappe.get_doc("Customer Group", filters["customer_group"])
		if cg.is_group == 1:
			child_cgs = frappe.db.sql("""SELECT name FROM `tabCustomer Group` 
				WHERE lft >= %s AND rgt <= %s""" %(cg.lft, cg.rgt), as_list = 1)
			for i in child_cgs:
				if child_cgs[0] == i:
					cond += " AND (cu.customer_group = '%s'" %i[0]
				elif child_cgs[len(child_cgs)-1] == i:
					cond += " OR cu.customer_group = '%s')" %i[0]
				else:
					cond += " OR cu.customer_group = '%s'" %i[0]
		else:
			cond += " AND cu.customer_group = '%s'" % filters["customer_group"]
	return cond
