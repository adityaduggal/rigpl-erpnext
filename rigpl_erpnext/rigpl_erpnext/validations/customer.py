# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from rigpl_erpnext.rigpl_erpnext.validations.lead import \
	create_new_user_perm, delete_unused_perm, find_total_perms, \
	check_system_manager, get_dl_parent
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
		
			
	for d in doc.sales_team:
		if d.sales_person:
			s_person = frappe.get_doc("Sales Person", d.sales_person)
			if s_person.employee:
				emp = frappe.get_doc("Employee", s_person.employee)
				if emp.status == "Active":
					if emp.user_id:
						check_sys = check_system_manager(emp.user_id)
						if check_sys == 1:
							pass
						else:
							allowed_ids.extend([emp.user_id])
							create_new_user_perm(doc.doctype, doc.name, emp.user_id)

				else:
					frappe.msgprint("Selected Sales Person is Not an Active Employee", raise_exception=1)
	if doc.default_sales_partner:
		s_partner = frappe.get_doc("Sales Partner", doc.default_sales_partner)
		if s_partner.user:
			user = frappe.get_doc("User", s_partner.user)
			check_sys = check_system_manager(user.name)
			if check_sys == 1:
				pass
			else:
				if user.enabled == 1:
					create_new_user_perm(doc.doctype, doc.name, s_partner.user)
					allowed_ids.extend([s_partner.user])
	if doc.customer_login_id:
		check_sys = check_system_manager(doc.customer_login_id)
		if check_sys == 1:
			pass
		else:
			create_new_user_perm(doc.doctype, doc.name, doc.customer_login_id)
			allowed_ids.extend([doc.customer_login_id])
	con_list = get_dl_parent(dt='Contact', linked_dt='Customer', linked_dn= doc.name)
	for contact in con_list:
		for user in allowed_ids:
			create_new_user_perm("Contact", contact[0], user)

	add_list = get_dl_parent(dt='Address', linked_dt='Customer', linked_dn= doc.name)
	for address in add_list:
		for user in allowed_ids:
			create_new_user_perm("Address", address[0], user)

	for d in [[doc.doctype, [doc.name]],["Address", add_list], ["Contact", con_list]]:
		for add in d[1]:
			total_perms = find_total_perms(d[0], add[0])
			if total_perms:
				for extra in total_perms:
					if extra[2] in allowed_ids:
						pass
					else:
						delete_unused_perm(extra[0], d[0], add[0], extra[2])

	total_perms = find_total_perms(doc.doctype, doc.name)
	if total_perms:
		for extra in total_perms:
			if extra[2] in allowed_ids:
				pass
			else:
				delete_unused_perm(extra[0], doc.doctype, doc.name, extra[2])

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