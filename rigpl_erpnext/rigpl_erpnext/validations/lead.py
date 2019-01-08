# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
import frappe.permissions
from rigpl_erpnext.utils.rigpl_perm import *

def validate(doc,method):
	if doc.lead_owner:
		if doc.lead_owner != doc.contact_by:
			doc.contact_by = doc.lead_owner

def on_update(doc,method):
	check_sys = 0
	#Lock Lead if its linked to a Customer so no editing on Lead is allowed
	check_conversion = frappe.db.sql("""SELECT name FROM `tabCustomer` 
		WHERE lead_name = '%s'"""%(doc.name), as_list=1)
	
	if check_conversion:
		frappe.throw(("Editing of Lead {0} NOT ALLOWED since its linked to Customer {1}. \
			Kindly add information to Customer Master and not Lead").format\
			(doc.name, check_conversion[0][0]))
	role_list = get_user_roles(doc.lead_owner)
	role_in_settings, apply_to_all_doctypes, applicable_for = \
		check_role(role_list, doctype="Lead", apply_to_all_doctypes="None")
	if doc.lead_owner:
		existing_perm = get_permission(allow=doc.doctype, for_value=doc.name, \
			user=doc.lead_owner, applicable_for=applicable_for, \
			apply_to_all_doctypes=apply_to_all_doctypes)
		if not existing_perm:
			if role_in_settings == 1:
				create_new_user_perm(allow=doc.doctype, for_value=doc.name, \
					user=doc.lead_owner, applicable_for=applicable_for, \
					apply_to_all_doctypes=apply_to_all_doctypes)
		extra_perm = get_extra_perms(allow="Lead", for_value=doc.name, \
			user=doc.lead_owner, apply_to_all_doctypes=1)
		if extra_perm:
			for perm in extra_perm:
				delete_permission(name=perm[0])
	add_list = get_dl_parent(dt='Address', linked_dt='Lead', linked_dn= doc.name)
	for address in add_list:
		if check_sys == 1:
			pass
		else:
			role_in_settings, apply_to_all_doctypes, applicable_for = \
				check_role(role_list, doctype="Address", apply_to_all_doctypes="None")
			if role_in_settings == 1:
				create_new_user_perm(allow="Address", for_value=address[0], \
					user=doc.lead_owner, applicable_for=applicable_for, \
					apply_to_all_doctypes=apply_to_all_doctypes)
		extra_perms = get_extra_perms(allow="Address", for_value=address[0], \
			user=doc.lead_owner, apply_to_all_doctypes=1)
		if extra_perms:
			for perm in extra_perms:
				delete_permission(name=perm[0])