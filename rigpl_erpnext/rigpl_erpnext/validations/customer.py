# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
import frappe.permissions

def on_update(doc,method):
	allowed_ids = []
	for d in doc.sales_team:
		if d.sales_person:
			s_person = frappe.get_doc("Sales Person", d.sales_person)
			if s_person.employee:
				emp = frappe.get_doc("Employee", s_person.employee)
				if emp.status == "Active":
					if emp.user_id:
						frappe.permissions.add_user_permission("Customer", doc.name, emp.user_id)
						allowed_ids.extend([emp.user_id])
				else:
					frappe.msgprint("Selected Sales Person is Not an Active Employee", raise_exception=1)
	if doc.default_sales_partner:
		s_partner = frappe.get_doc("Sales Partner", doc.default_sales_partner)
		if s_partner.user:
			user = frappe.get_doc("User", s_partner.user)
			if user.enabled == 1:
				frappe.permissions.add_user_permission("Customer", doc.name, s_partner.user)
				allowed_ids.extend([s_partner.user])
	
	query = """SELECT name, parent from `tabDefaultValue` where defkey = 'Customer' AND defvalue = '%s'""" % (doc.name)
	extra_perm = frappe.db.sql(query, as_list=1)
	if extra_perm <> []:
		for i in range(len(extra_perm)):
			if extra_perm[i][1] in allowed_ids:
				pass
			else:
				frappe.permissions.remove_user_permission("Customer", doc.name, extra_perm[i][1])