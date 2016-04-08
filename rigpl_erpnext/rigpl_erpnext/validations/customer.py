# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
import frappe.permissions

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
	if doc.customer_login_id:
		frappe.permissions.add_user_permission("Customer", doc.name, doc.customer_login_id)
		allowed_ids.extend([doc.customer_login_id])
	
	query = """SELECT name, parent from `tabDefaultValue` where defkey = 'Customer' AND defvalue = '%s'""" % (doc.name)
	extra_perm = frappe.db.sql(query, as_list=1)
	if extra_perm <> []:
		for i in range(len(extra_perm)):
			if extra_perm[i][1] in allowed_ids:
				pass
			else:
				frappe.permissions.remove_user_permission("Customer", doc.name, extra_perm[i][1])