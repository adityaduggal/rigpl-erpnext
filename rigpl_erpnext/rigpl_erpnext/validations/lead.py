# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
import frappe.permissions

def validate(doc,method):
	if doc.lead_owner:
		if doc.lead_owner != doc.contact_by:
			doc.contact_by = doc.lead_owner

def on_update(doc,method):
	#Lock Lead if its linked to a Customer so no editing on Lead is allowed
	check_conversion = frappe.db.sql("""SELECT name FROM `tabCustomer` 
		WHERE lead_name = '%s'"""%(doc.name), as_list=1)
	
	if check_conversion:
		frappe.throw(("Editing of Lead {0} NOT ALLOWED since its linked to Customer {1}. \
			Kindly add information to Customer Master and not Lead").format\
			(doc.name, check_conversion[0][0]))
	if doc.lead_owner:
		existing_perm = check_existing_permission(doc.doctype, doc.name, doc.lead_owner)
		if not existing_perm:
			create_new_user_perm(doc.doctype, doc.name, doc.lead_owner)
	extra_perm = get_extra_perms(doc.doctype, doc.name, doc.lead_owner)
	if extra_perm:
		for perm in extra_perm:
			delete_unused_perm(perm[0], doc.doctype, doc.name, perm[2])

def check_existing_permission(doctype, docname, user):
	existing_perm = frappe.db.sql("""SELECT name, for_value, user FROM `tabUser Permission` 
		WHERE allow = '%s' AND for_value = '%s' AND user = '%s'""" 
		%(doctype, docname, user), as_list = 1)
	return existing_perm

def create_new_user_perm(doctype, docname, user):
	existing_perm = check_existing_permission(doctype, docname, user)
	if not existing_perm:
		new_perm = frappe.new_doc("User Permission")
		new_perm.flags.ignore_permissions = True
		new_perm.user = user
		new_perm.allow = doctype
		new_perm.for_value = docname
		new_perm.apply_for_all_roles = 0
		new_perm.insert()
		frappe.msgprint(("Added New Permission for {0}: {1} for User: {2}").format(doctype, docname, user))
		frappe.db.commit()

def get_extra_perms(doctype, docname, user):
	query = """SELECT name, for_value, user from  `tabUser Permission` where allow = '%s' AND for_value = '%s' 
		AND user != '%s' """ % (doctype, docname, user)
	extra_perm = frappe.db.sql(query, as_list=1)

	return extra_perm

def delete_unused_perm(perm_name, doctype, docname, user):
	delete_perm = frappe.get_doc("User Permission", perm_name)
	delete_perm.flags.ignore_permissions = True
	delete_perm.delete()
	frappe.msgprint(("Deleted Permission for \
		{0}: {1} for User: {2}").format(doctype, docname, user))

def find_total_perms(doctype, docname):
	total_perms = frappe.db.sql("""SELECT name, for_value, user from  `tabUser Permission` 
		WHERE allow = '%s' AND for_value = '%s'""" % (doctype, docname), as_list=1)
	return total_perms