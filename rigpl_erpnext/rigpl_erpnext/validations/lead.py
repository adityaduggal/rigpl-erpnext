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
		frappe.permissions.add_user_permission("Lead", doc.name, doc.lead_owner)
		if doc.lead_owner <> doc.contact_by:
			frappe.db.set_value("Lead", doc.name, "contact_by", doc.lead_owner)
	
	#Check if the lead is not in another user, if its there then delete the LEAD 
	#from the user's permission
	query = """SELECT name, parent from `tabDefaultValue` where defkey = 'Lead' AND defvalue = '%s' 
		AND parent <> '%s' """ % (doc.name, doc.lead_owner)
	extra_perm = frappe.db.sql(query, as_list=1)
	if extra_perm <> []:
		for i in range(len(extra_perm)):
			frappe.permissions.remove_user_permission("Lead", doc.name, extra_perm[i][1])
	