# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
import frappe.permissions

def on_update(doc,method):
	#Lock Lead if its linked to a Customer so no editing on Lead is allowed
	check_conversion = frappe.db.sql("""SELECT name FROM `tabCustomer` 
		WHERE lead_name = '%s'"""%(doc.name), as_list=1)
	
	if check_conversion:
		frappe.throw(("Editing of Lead {0} NOT ALLOWED since its linked to Customer {1}. \
			Kindly add information to Customer Master and not Lead").format\
			(doc.name, check_conversion[0][0]))
	
	if doc.lead_owner:
		existing_perm = frappe.db.sql("""SELECT name, for_value, user FROM `tabUser Permission` WHERE allow = 'Lead' AND
		for_value = '%s' AND user <> '%s'""" %(doc.name, doc.lead_owner), as_list = 1)
		if existing_perm is None:
			new_perm = frappe.new_doc("User Permission")
			new_perm.user = doc.lead_owner
			new_perm.allow = "Lead"
			new_perm.for_value = doc.name
			new_perm.apply_for_all_roles = 1
			new_perm.flags.ignore_permissions = True
			new_perm.insert()
		if doc.lead_owner != doc.contact_by:
			doc.contact_by = doc.lead_owner
	
	#Check if the lead is not in another user, if its there then delete the LEAD 
	#from the user's permission
	query = """SELECT name, for_value, user from  `tabUser Permission` where allow = 'Lead' AND for_value = '%s' 
		AND user <> '%s' """ % (doc.name, doc.lead_owner)
	extra_perm = frappe.db.sql(query, as_list=1)
	if extra_perm != []:
		for i in range(len(extra_perm)):
			delete_perm = frappe.get_doc("User Permission", extra_perm[i][0])
			delete_perm.flags.ignore_permissions = True
			delete_perm.delete()	