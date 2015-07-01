# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
import frappe.permissions

def on_update(doc,method):
	if doc.lead_owner:
		frappe.permissions.add_user_permission("Lead", doc.name, doc.lead_owner)
		if doc.lead_owner <> doc.contact_by:
			frappe.db.set_value("Lead", doc.name, "contact_by", doc.lead_owner)
	
	#Check if the lead is not in another user, if its there then delete the LEAD from the user's permission
	query = """SELECT name, parent from `tabDefaultValue` where defkey = 'Lead' AND defvalue = '%s' AND parent <> '%s' """ % (doc.name, doc.lead_owner)
	extra_perm = frappe.db.sql(query, as_list=1)
	if extra_perm <> []:
		for i in range(len(extra_perm)):
			frappe.permissions.remove_user_permission("Lead", doc.name, extra_perm[i][1])
	