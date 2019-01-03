# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from rigpl_erpnext.utils.rigpl_perm import *
import frappe.permissions
import re

def on_update(doc,method):
	allowed_ids = []
	#Check if Customer Login ID is not Repeated
	if doc.customer_login_id:
		other_login_id = frappe.db.sql("""SELECT name FROM `tabCustomer` 
			WHERE customer_login_id = '%s' 
			AND name != '%s'""" %(doc.customer_login_id, doc.name), as_list=1)
		if other_login_id:
			frappe.throw(("Customer {0} already linked to User ID {1}").format(other_login_id[0][0], \
				doc.customer_login_id))
	#Check for From Lead field and don't allow duplication.
	if doc.lead_name:
		other_lead = frappe.db.sql("""SELECT name FROM `tabCustomer` 
			WHERE lead_name = '%s' AND name != '%s' """ %(doc.lead_name, doc.name), as_list=1)
		if other_lead:
			frappe.throw(("Lead {0} already linked to Customer {1}").format(doc.lead_name, \
			other_lead[0][0]))
		else:
			#Check all previous quotations and Opportunity on Lead and add the name of Customer
			quote = frappe.db.sql("""SELECT name FROM `tabQuotation` 
				WHERE lead = '%s' AND (customer IS NULL OR customer = '')"""%(doc.lead_name), as_list=1)
			opp = frappe.db.sql("""SELECT name FROM `tabOpportunity` 
				WHERE lead = '%s' AND (customer IS NULL OR customer = '')"""%(doc.lead_name), as_list=1)
			if quote:
				for i in quote:
					frappe.db.set_value("Quotation", i[0], "customer", doc.name)
			if opp:
				for i in opp:
					frappe.db.set_value("Opportunity", i[0], "customer", doc.name)
	else:
		#Check if any Quote or Opportunity is linked to Customer with Lead and if so Remove it.
		quote = frappe.db.sql("""SELECT name FROM `tabQuotation` 
			WHERE customer = '%s' AND (lead IS NOT NULL OR lead = '')""" %(doc.name), as_list=1)
		opp = frappe.db.sql("""SELECT name FROM `tabOpportunity` 
			WHERE customer = '%s' AND (lead IS NOT NULL OR lead = '')""" %(doc.name), as_list=1)
		if quote:
			for i in quote:
				frappe.db.set_value("Quotation", i[0], "customer", None)
		if opp:
			for i in opp:
				frappe.db.set_value("Opportunity", i[0], "customer", None)
		
			
	allowed_ids = get_customer_allowed_ids(doc.name)
	for user in allowed_ids:
		role_list = get_user_roles(user)
		role_in_settings, apply_to_all_doctypes, applicable_for = \
			check_role(role_list, "Customer", apply_to_all_doctypes="None")
		if role_in_settings == 1:
			create_new_user_perm(allow="Customer", for_value=doc.name, \
				user=user, apply_to_all_doctypes=apply_to_all_doctypes, \
				applicable_for=applicable_for)

	con_list = get_dl_parent(dt='Contact', linked_dt='Customer', linked_dn= doc.name)
	for contact in con_list:
		for user in allowed_ids:
			role_list = get_user_roles(user)
			role_in_settings, apply_to_all_doctypes, applicable_for = \
				check_role(role_list, "Contact", apply_to_all_doctypes="None")
			if role_in_settings == 1:
				create_new_user_perm(allow="Contact", for_value=contact[0], \
					user=user, apply_to_all_doctypes=apply_to_all_doctypes, \
					applicable_for=applicable_for)

	add_list = get_dl_parent(dt='Address', linked_dt='Customer', linked_dn= doc.name)
	for address in add_list:
		for user in allowed_ids:
			role_list = get_user_roles(user)
			role_in_settings, apply_to_all_doctypes, applicable_for = \
				check_role(role_list, "Address", apply_to_all_doctypes="None")
			if role_in_settings == 1:
				create_new_user_perm(allow="Address", for_value=address[0], \
					user=user, apply_to_all_doctypes=apply_to_all_doctypes, \
					applicable_for=applicable_for)

	cust_perm_list = get_permission(allow="Customer", for_value=doc.name)
	con_perm_list = []
	add_perm_list = []
	if con_list:
		for contact in con_list:
			con_perm_list_temp = get_permission(allow="Contact", for_value=contact[0])
			con_perm_list.extend(con_perm_list_temp)
	if add_list:
		for add in add_list:
			add_perm_list_temp = get_permission(allow="Address", for_value=add[0])
			add_perm_list.extend(add_perm_list_temp)
	for perm in cust_perm_list:
		if perm[3] not in allowed_ids:
			delete_permission(perm[0])
	for perm in add_perm_list:
		if perm[3] not in allowed_ids:
			delete_permission(perm[0])
	for perm in con_perm_list:
		if perm[3] not in allowed_ids:
			delete_permission(perm[0]) 		


def validate(doc,method):
	new_name, entered_name = check_customer_id (doc,method)
	if doc.get('__islocal'):
		if new_name != doc.name:
			doc.customer_name = entered_name
			doc.name = new_name
	else:
		if new_name != doc.name:
			frappe.throw(("Special Characters not allowed in Customer ID.\
				Current Customer ID: {0}-->Allowed Customer ID: {1}").format(doc.name, new_name))

def check_customer_id(doc,method):
	#Disallow Special Characters in Customer ID
	new_name = re.sub('[^A-Za-z0-9]+', '', doc.name)
	entered_name = doc.name
	return new_name, entered_name