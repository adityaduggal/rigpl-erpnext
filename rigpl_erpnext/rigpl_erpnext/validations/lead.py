# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.share import add, remove
import frappe.permissions
from rigpl_erpnext.utils.rigpl_perm import *

def validate(doc,method):
	if doc.lead_owner:
		if doc.lead_owner != doc.contact_by:
			doc.contact_by = doc.lead_owner
	if doc.campaign_name != 'India Mart':
		if not doc.email_id:
			frappe.throw('Email ID is Mandatory')
	lead_docshare(doc)
	lead_quote_share(doc)
	lead_address_share(doc)

def on_update(doc,method):
	check_sys = 0
	#Lock Lead if its linked to a Customer so no editing on Lead is allowed
	check_conversion = frappe.db.sql("""SELECT name FROM `tabCustomer` 
		WHERE lead_name = '%s'"""%(doc.name), as_list=1)
	
	if check_conversion:
		frappe.throw(("Editing of Lead {0} NOT ALLOWED since its linked to Customer {1}. \
			Kindly add information to Customer Master and not Lead").format\
			(doc.name, check_conversion[0][0]))

def lead_docshare(lead_doc):
	check_sys = 0
	emp_stat = frappe.get_value("User", lead_doc.lead_owner, "enabled")
	if lead_doc.owner != lead_doc.lead_owner:
		role_list = get_user_roles(lead_doc.lead_owner)
		check_sys = check_system_manager(user=lead_doc.lead_owner)
	else:
		role_list = []
	if check_sys != 1 and emp_stat == 1 and role_list:
		role_in_settings, write_access,share_access, notify_by_email = \
			check_role_usershare(role_list=role_list, doctype=lead_doc.doctype)
		if role_in_settings:
			shared_dict = get_shared(document_type=lead_doc.doctype, document_name=lead_doc.name)
			user_in_shared_dict = 0
			if shared_dict:
				for shared_doc in shared_dict:
					if shared_doc.user != lead_doc.lead_owner:
						remove(lead_doc.doctype, lead_doc.name, shared_doc.user)
					else:
						user_in_shared_dict = 1
			if user_in_shared_dict != 1:
				add(lead_doc.doctype, lead_doc.name, user=lead_doc.lead_owner, write=write_access, \
					share=share_access, notify=notify_by_email)

def lead_quote_share(lead_doc):
	check_sys = 0
	emp_stat = frappe.get_value("User", lead_doc.lead_owner, "enabled")
	quote_dict = frappe.db.sql("""SELECT name FROM `tabQuotation` 
		WHERE lead = '%s' AND customer IS NULL""" %(lead_doc.name), as_dict=1)
	if quote_dict:
		for quote in quote_dict:
			quote_doc = frappe.get_doc("Quotation", quote.name)
			if quote_doc.owner != lead_doc.lead_owner:
				#Create Share for Quote
				role_list = get_user_roles(lead_doc.lead_owner)
				check_sys = check_system_manager(user=lead_doc.lead_owner)
			else:
				role_list = []
			if check_sys != 1 and emp_stat == 1 and role_list:
				role_in_settings, write_access,share_access, notify_by_email = \
					check_role_usershare(role_list=role_list, doctype=quote_doc.doctype)
				if role_in_settings:
					shared_dict = get_shared(document_type=quote_doc.doctype, document_name=quote_doc.name)
					user_in_shared_dict = 0
					if shared_dict:
						for shared_doc in shared_dict:
							if shared_doc.user != lead_doc.lead_owner:
								remove(quote_doc.doctype, quote_doc.name, shared_doc.user)
							else:
								user_in_shared_dict = 1
					if user_in_shared_dict != 1:
						add(quote_doc.doctype, quote_doc.name, user=lead_doc.lead_owner, write=write_access, \
							share=share_access, notify=notify_by_email)

def lead_address_share(lead_doc):
	check_sys = 0
	emp_stat = frappe.get_value("User", lead_doc.lead_owner, "enabled")

	add_dict = frappe.db.sql("""SELECT parent 
		FROM `tabDynamic Link`
		WHERE parenttype = 'Address' AND link_doctype = '%s' 
		AND link_name = '%s'""" %(lead_doc.doctype, lead_doc.name), as_dict=1)
	if add_dict:
		for address in add_dict:
			add_doc = frappe.get_doc("Address", address.parent)
			if add_doc.owner != lead_doc.lead_owner:
				#Create Share for Quote
				role_list = get_user_roles(lead_doc.lead_owner)
				check_sys = check_system_manager(user=lead_doc.lead_owner)
			else:
				role_list = []
			if check_sys != 1 and emp_stat == 1 and role_list:
				role_in_settings, write_access,share_access, notify_by_email = \
					check_role_usershare(role_list=role_list, doctype=add_doc.doctype)
				if role_in_settings:
					shared_dict = get_shared(document_type=add_doc.doctype, document_name=add_doc.name)
					user_in_shared_dict = 0
					if shared_dict:
						for shared_doc in shared_dict:
							if shared_doc.user != lead_doc.lead_owner:
								remove(add_doc.doctype, add_doc.name, shared_doc.user)
							else:
								user_in_shared_dict = 1
					if user_in_shared_dict != 1:
						add(add_doc.doctype, add_doc.name, user=lead_doc.lead_owner, write=write_access, \
							share=share_access, notify=notify_by_email)