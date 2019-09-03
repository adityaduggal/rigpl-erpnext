# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def execute():
	cust_list = frappe.db.sql("""SELECT name FROM `tabCustomer` WHERE customer_primary_contact IS NULL""", as_list=1)
	if cust_list:
		for cu in cust_list:
			print("Checking " + cu[0])
			contacts = frappe.db.sql("""SELECT cu.name FROM `tabContact` cu, `tabDynamic Link` dl 
				WHERE dl.parent = cu.name AND dl.link_doctype = 'Customer' 
				AND dl.link_name = '%s'"""%(cu[0]), as_list=1)
			if contacts:
				if len(contacts) == 1:
					set_primary_contact(cu[0], contacts[0][0])
				else:
					for cont in contacts:
						cont_doc = frappe.get_doc("Contact", cont[0])
						if cont_doc.is_primary_contact:
							set_primary_contact(cu[0], cont[0])

		
	cust_add_list = frappe.db.sql("""SELECT name FROM `tabCustomer` WHERE customer_primary_address IS NULL""", as_list=1)
	if cust_add_list:
		for cu in cust_list:
			print("Checking " + cu[0])
			addresses = frappe.db.sql("""SELECT cu.name FROM `tabAddress` cu, `tabDynamic Link` dl 
				WHERE dl.parent = cu.name AND dl.link_doctype = 'Customer' 
				AND dl.link_name = '%s'"""%(cu[0]), as_list=1)
			if addresses:
				if len(addresses) == 1:
					set_primary_address(cu[0], addresses[0][0])
				else:
					for address in addresses:
						add_doc = frappe.get_doc("Address", address[0])
						if cont_doc.is_primary_contact:
							set_primary_address(cu[0], address[0])

	cust_st_list = frappe.db.sql("""SELECT cu.name FROM `tabCustomer` cu
		WHERE cu.name NOT IN (SELECT cu.name FROM `tabCustomer` cu, `tabSales Team` st 
		WHERE st.parenttype = 'Customer' AND st.parent = cu.name)""", as_list=1)

	print("Total Number of Customers without Primary Contact = " + str(len(cust_list)))							
	print("Total Number of Customers without Primary Address = " + str(len(cust_add_list)))
	print("Total Number of Customers without Sales Team = " + str(len(cust_st_list)))

def set_primary_contact(cust_id, contact_id):
	cont_doc = frappe.get_doc("Contact", contact_id)
	frappe.db.set_value("Customer", cust_id, "customer_primary_contact", contact_id)
	frappe.db.set_value("Customer", cust_id, "mobile_no", cont_doc.mobile_no)
	frappe.db.set_value("Customer", cust_id, "email_id", cont_doc.email_id)
	print("Customer " + cust_id + " Updated with Primary Contact of " + contact_id)

def set_primary_address(cust_id, add_id):
	add_doc = frappe.get_doc("Address", add_id)
	frappe.db.set_value("Customer", cust_id, "customer_primary_address", add_id)
	from frappe.contacts.doctype.address.address import get_address_display
	frappe.db.set_value("Customer", cust_id, "primary_address", get_address_display(add_id))
	print("Customer " + cust_id + " Updated with Primary Address of " + add_id)