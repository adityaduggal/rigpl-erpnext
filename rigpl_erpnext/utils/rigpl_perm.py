# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def create_new_user_perm(allow=None, for_value=None, user=None, applicable_for=None, \
	apply_to_all_doctypes=None):
	existing_perm = get_permission(allow=allow, for_value=for_value, user=user, \
		applicable_for=applicable_for, apply_to_all_doctypes=apply_to_all_doctypes)
	#print(existing_perm)
	if not existing_perm:
		#check_settings(allow, for_value, applicable_for, apply_to_all_doctypes)
		new_perm = frappe.new_doc("User Permission")
		new_perm.flags.ignore_permissions = True
		new_perm.user = user
		new_perm.allow = allow
		new_perm.for_value = for_value
		new_perm.apply_to_all_doctypes = apply_to_all_doctypes
		new_perm.applicable_for = applicable_for
		new_perm.insert()
		frappe.msgprint(("Added New Permission for {0}: {1} for User: {2}").format(allow, for_value, user))
		print("Added New Permission for " + allow + ": " + for_value + " for User: " + user)
		frappe.db.commit()

def check_system_manager(user=None):
	sysmgr_list = frappe.db.sql("""SELECT name FROM `tabHas Role` 
		WHERE parenttype = 'User' AND parent = '%s' 
		AND role = 'System Manager'"""%(user), as_list = 1)
	if sysmgr_list:
		return 1
	else:
		return 0

def get_dl_parent(dt, linked_dt, linked_dn):
	dl_parent_list = frappe.db.sql("""SELECT parent FROM `tabDynamic Link` 
		WHERE parenttype = '%s' AND link_doctype = '%s'
		AND link_name = '%s'"""%(dt,linked_dt, linked_dn), as_list=1)
	if not dl_parent_list:
		dl_parent_list = []
	return dl_parent_list

def delete_version(document, creator=None, creation=None):
	commit_chk = 0
	conditions = ''
	if creator:
		conditions += " AND owner = '%s'" %(creator)
	
	if creation:
		conditions += " AND creation <= DATE_SUB(NOW(), INTERVAL %s DAY)"%(creation)

	version_list = frappe.db.sql("""SELECT name FROM `tabVersion` 
		WHERE ref_doctype = '%s' %s""" %(document, conditions), as_list=1)
	if version_list:
		for version in version_list:
			frappe.db.sql("""DELETE FROM `tabVersion` WHERE name = '%s'"""%(version[0]))
			commit_chk += 1
			if commit_chk%1000 == 0:
				frappe.db.commit()
			print(str(commit_chk) + ". Deleted Version: " + version[0])

def delete_from_deleted_doc(document):
	commit_chk = 0
	del_doc_list = frappe.db.sql("""SELECT name FROM `tabDeleted Document` 
		WHERE deleted_doctype = '%s'"""%(document), as_list=1)
	if del_doc_list:
		for del_doc in del_doc_list:
			frappe.db.sql("""DELETE FROM `tabDeleted Document` 
				WHERE name = '%s'"""%(del_doc[0]))
			commit_chk += 1
			if commit_chk%1000 == 0:
				frappe.db.commit()
			print(str(commit_chk) + ". Deleted " + del_doc[0])

def get_user_lead(user):
	lead_list = frappe.db.sql("""SELECT name FROM `tabLead` 
		WHERE lead_owner = '%s'"""%(user), as_list=1)
	if not lead_list:
		lead_list = []
	return lead_list

def get_cust_from_sperson(s_person, parenttype):
	query = """SELECT parent FROM `tabSales Team` 
		WHERE parenttype = '%s' AND sales_person = '%s'"""%(parenttype, s_person)
	cust_list = frappe.db.sql(query, as_list=1)
	if not cust_list:
		cust_list=[]
	return cust_list

def get_sales_person(employee):
	s_person = frappe.db.sql("""SELECT name FROM `tabSales Person` 
		WHERE employee = '%s' AND enabled = 1"""%(employee), as_list=1)
	if not s_person:
		s_person = []
	return s_person

def get_user_emp(user_id):
	emp = frappe.db.sql("""SELECT name FROM `tabEmployee` 
		WHERE user_id = '%s'"""%(user_id), as_list=1)
	if not emp:
		emp = []
	return emp

def get_users(active=0):
	users = frappe.db.sql("""SELECT name FROM `tabUser`
		WHERE enabled = %s"""%(active), as_list=1)
	return users

def get_employees(status=None):
	conditions = ''
	if status:
		conditions += " AND status = '%s'" %(status)
	emp_list = frappe.db.sql("""SELECT name FROM `tabEmployee`
		WHERE docstatus = 0 %s """%(conditions), as_list=1)
	return emp_list

def get_employees_allowed_ids(employee):
	allowed_ids = []
	department = frappe.get_value("Employee", employee, "department")
	user_id = frappe.get_value("Employee", employee, "user_id")
	user_id_perm = frappe.get_value("Employee", employee, "create_user_permission")
	reports_to = frappe.get_value("Employee", employee, "reports_to")
	if user_id is not None and user_id_perm == 1:
		check_sys = check_system_manager(user_id)
		if check_sys != 1:
			allowed_ids.append(user_id)
	if reports_to:
		check_sys = check_system_manager(reports_to)
		if check_sys != 1:
			allowed_ids.append(reports_to)
	if department:
		dep_doc = frappe.get_doc("Department", department)
	else:
		print("No Department Defined for Employee: " + employee)
	if dep_doc:
		for la in dep_doc.leave_approvers:
			if la.approver:
				check_sys = check_system_manager(la.approver)
				if check_sys != 1:
					allowed_ids.extend([la.approver])
	return allowed_ids

def get_customer_allowed_ids(customer):
	allowed_ids = []
	customer_doc = frappe.get_doc("Customer", customer)
	for sperson in customer_doc.sales_team:
		if sperson.sales_person:
			s_person_emp = frappe.get_value("Sales Person", sperson.sales_person, "employee")
			if s_person_emp:
				emp_doc = frappe.get_doc("Employee", s_person_emp)
				if emp_doc.status == "Active":
					if  emp_doc.user_id:
						check_sys = check_system_manager(emp_doc.user_id)
						if check_sys != 1:
							allowed_ids.extend([emp_doc.user_id])
	if customer_doc.customer_login_id:
		check_sys = check_system_manager(customer_doc.customer_login_id)
		if check_sys != 1:
			allowed_ids.extend([customer_doc.customer_login_id])
	if customer_doc.default_sales_partner:
		s_partner = frappe.get_doc("Sales Partner", customer_doc.default_sales_partner)
		if s_partner.user:
			user = frappe.get_doc("User", s_partner.user)
			check_sys = check_system_manager(user.name)
			if check_sys != 1:
				if user.enabled == 1:
					allowed_ids.extend([s_partner.user])
	return allowed_ids

def get_extra_perms(allow, for_value, user, apply_to_all_doctypes=None, \
	applicable_for=None):
	conditions = ""
	if applicable_for:
		conditions += " AND applicable_for = '%s'" %(applicable_for)
	if apply_to_all_doctypes == 1:
		conditions += " AND apply_to_all_doctypes = 1"
	elif apply_to_all_doctypes == 'None':
		pass
	else:
		conditions += " AND apply_to_all_doctypes = 0"
	query = """SELECT name, for_value, user from  `tabUser Permission` 
		WHERE allow = '%s' AND for_value = '%s' 
		AND user != '%s' %s""" % (allow, for_value, user, conditions)
	extra_perm = frappe.db.sql(query, as_list=1)
	return extra_perm

def get_permission(name=None, user=None, allow=None, for_value=None, \
	applicable_for = None, apply_to_all_doctypes=None, deleted=None):
	conditions = ''
	if name:
		conditions += " AND name = '%s'"%(name)
	if user:
		conditions += " AND user = '%s'"%(user)
	if allow:
		conditions += " AND allow = '%s'"%(allow)
	if for_value:
		conditions += " AND for_value = '%s'"%(for_value)
	if applicable_for:
		conditions += " AND applicable_for = '%s'"%(applicable_for)
	if apply_to_all_doctypes==1:
		conditions += " AND apply_to_all_doctypes = 1"
	elif apply_to_all_doctypes == "None":
		conditions += " AND apply_to_all_doctypes = 0"
	else:
		pass

	query = """SELECT name, allow, for_value, user, applicable_for, 
		apply_to_all_doctypes
		FROM `tabUser Permission` WHERE docstatus = 0 %s"""%(conditions)
	permission_list = frappe.db.sql(query , as_list=1)

	return permission_list

def delete_permission(name=None, user=None, allow=None, for_value=None, \
	applicable_for=None, apply_to_all_doctypes=None):
	permission_list = get_permission(name=name, user=user, allow=allow, \
		for_value=for_value, applicable_for=applicable_for, \
		apply_to_all_doctypes=apply_to_all_doctypes)
	for perm in permission_list:
		frappe.db.sql("""DELETE FROM `tabUser Permission` 
			WHERE name = '%s'"""%(perm[0]))
		#frappe.delete_doc_if_exists("User Permission", perm[0])
		frappe.msgprint("Deleted User Permission: {} for User: {} for Doctype: {} \
			for Value: {}".format(perm[0], perm[3], perm[1], perm[2]))

		print ('Deleted User Permission: ' + perm[0] + ' for User: ' + perm[3] \
			+ ' for Doctype ' + perm[1] + " Value " + perm[2])

def restore_deleted_permission(name):
	restore(name)

def clean_dynamic_link_table():
	query = """SELECT name FROM `tabDynamic Link` 
		WHERE parenttype = 'Contact' 
		AND parent NOT IN (SELECT name FROM `tabContact`)"""
	wrong_contact_list = frappe.db.sql(query, as_list=1)
	for contact in wrong_contact_list:
		print (contact)

	query = """SELECT name FROM `tabDynamic Link` 
		WHERE parenttype = 'Address' 
		AND parent NOT IN (SELECT name FROM `tabAddress`)"""
	wrong_add_list = frappe.db.sql(query, as_list=1)
	if wrong_add_list:
		for address in wrong_add_list:
			frappe.delete_doc_if_exists("Dynamic Link", address[0])
			frappe.db.commit()
			print("Deleted Dynamic Link " + address[0])

def clean_sales_team_table():
	query = """SELECT name, parent FROM `tabSales Team` WHERE parenttype = 'Customer' 
	AND parent NOT IN (SELECT name FROM `tabCustomer`) """
	list_of_st = frappe.db.sql(query, as_list=1)
	if list_of_st:
		for steam_lst in list_of_st:
			frappe.delete_doc_if_exists("Sales Team", steam_lst[0])
			frappe.db.commit()
			print ("Deleted Sales Team Data " + steam_lst[0] + " For Customer: " + steam_lst[1])

def get_user_roles(user):
	role_list = frappe.db.sql("""SELECT role FROM `tabHas Role` 
		WHERE parent = '%s' AND parenttype = 'User'"""%(user), as_list=1)
	return role_list

def get_user_perm_settings(allow=None, role=None, apply_to_all_roles=None, \
	apply_to_all_values=0, apply_to_all_doctypes=None):
	#This would check if the user permission needs to be created or not.
	conditions = ""
	if allow:
		conditions += " AND allow_doctype = '%s'"%(allow)
	if role:
		conditions += " AND role = '%s'"%(role)
	if apply_to_all_roles:
		conditions += " AND apply_to_all_roles = %s"%(apply_to_all_roles)
	if apply_to_all_values:
		conditions += " AND apply_to_all_values = %s"%(apply_to_all_values)
	if apply_to_all_doctypes==1:
		conditions += " AND apply_to_all_doctypes = 1"
	elif apply_to_all_doctypes == 'None':
		pass
	else:
		conditions += " AND apply_to_all_doctypes = 0"

	query = """SELECT role, allow_doctype, allow_doctype_value, 
		applicable_for_doctype, apply_to_all_doctypes
		FROM `tabUser Permission Rules` WHERE parent = 'User Permission Settings' 
		AND parentfield = 'rules' %s"""\
		%(conditions)
	#print(query)
	settings_list = frappe.db.sql(query, as_list=1)
	return settings_list

def delete_extra_perms():
	#Below code would check if there are permissions with ALL DT checked and
	#then delete any perms which is for same value with specific DT
	all_dt_perms = get_permission(apply_to_all_doctypes=1)
	commit_chk = 0
	for perm in all_dt_perms:
		print("Checking Permission for User:" + perm[3] + " with ID: " + perm[0])
		extra_perm = get_permission(allow=perm[1], for_value=perm[2], \
			user=perm[3], apply_to_all_doctypes="None")
		for et_perm in extra_perm:
			commit_chk += 1
			delete_permission(name=et_perm[0])
			if commit_chk%1000 == 0:
				frappe.db.commit()
	#Check User Perms for items not for their Roles
	#active_users = get_users(active=1)
	'''
	for user in active_users:
		role_list = get_user_roles(user[0])
		user_perms = get_permission(user=user[0])
		for perm in user_perms:
			print("Checking Permission for User: " + user[0] + " with ID: " + perm[0])
			role_in_settings, apply_to_all_doctypes, applicable_for = \
				check_role(role_list, doctype=perm[1], apply_to_all_doctypes="None")
			if role_in_settings==1:
				if apply_to_all_doctypes == perm[5] and applicable_for == perm[4]:
					pass
				else:
					delete_permission(name=perm[0])
			else:
				delete_permission(name=perm[0])
	'''

def check_role(role_list, doctype, apply_to_all_doctypes=None):
	role_in_settings = 0
	settings_list = get_user_perm_settings(allow=doctype, \
		apply_to_all_values=1, apply_to_all_doctypes=apply_to_all_doctypes)
	if settings_list:
		for set_list in settings_list:
			applicable_for = set_list[3]
			apply_to_all_doctypes = set_list[4]
			for role in role_list:
				if role[0] == set_list[0]:
					role_in_settings = 1
	else:
		role_in_settings = 0
		apply_to_all_doctypes = 0
		applicable_for = 0
	return role_in_settings, apply_to_all_doctypes, applicable_for