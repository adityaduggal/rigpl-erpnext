# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def create_new_user_perm(user, allow=None, for_value=None, applicable_for=None, \
	apply_to_all_doctypes=None):
	sysmgr = check_system_manager(user)
	enabled_user = frappe.get_value("User", user, "enabled")
	existing_perm = get_permission(allow=allow, for_value=for_value, user=user, \
		applicable_for=applicable_for, apply_to_all_doctypes=apply_to_all_doctypes)
	if sysmgr != 1 and enabled_user == 1:
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
			frappe.msgprint(("Added New Permission for {0}: {1} for User: {2}").\
				format(allow, for_value, user))
			print("Added New Permission for " + allow + ": " + for_value + " for User: " + user)
			frappe.db.commit()
	else:
		if existing_perm:
			for perm in existing_perm:
				frappe.msgprint(str(perm))
				delete_permission(name=perm[0])

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

def get_docshare(name=None, user=None, share_doctype=None, share_name=None):
	conditions = ''
	if name:
		conditions += " AND name = '%s'"%(name)
	if user:
		conditions += " AND user = '%s'"%(user)
	if share_doctype:
		conditions += " AND share_doctype = '%s'"%(share_doctype)
	if share_name:
		conditions += " AND share_name = '%s'"%(share_name)
	query = """SELECT name, share_doctype, share_name, user, `read`, `write`, share, everyone, notify_by_email
		FROM `tabDocShare` WHERE docstatus = 0 %s"""%(conditions)
	docshare_list = frappe.db.sql(query , as_dict=1)
	return docshare_list

def delete_docshare(name=None, user=None, share_doctype=None, share_name=None):
	docshare_list = get_docshare(name=name, user=user, share_doctype=share_doctype, \
		share_name=share_name)
	for docsh in docshare_list:
		frappe.db.sql("""DELETE FROM `tabDocShare` 
			WHERE name = '%s'"""%(docsh.name))
		#frappe.delete_doc_if_exists("User Permission", perm[0])
		frappe.msgprint("Deleted DocShare: {} for User: {} for Doctype: {} \
			for Value: {}".format(docsh.name, docsh.user, docsh.share_doctype, \
				docsh.share_name))

		print ('Deleted DocShare: ' + docsh.name + ' for User: ' + docsh.user \
			+ ' for Doctype ' + docsh.share_doctype + " Value " + docsh.share_name)

def check_system_manager(user):
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
	status = frappe.get_value("Employee", employee, "status")
	if status == 'Active':
		user_id = frappe.get_value("Employee", employee, "user_id")
		user_id_perm = frappe.get_value("Employee", employee, "create_user_permission")
		reports_to = frappe.get_value("Employee", employee, "reports_to")
		if user_id is not None and user_id_perm == 1:
			allowed_ids.append(user_id)
		if reports_to:
			allowed_ids.append(reports_to)
	return allowed_ids

def get_department_allowed_ids(dept_doc):
	allowed_ids = []
	if dept_doc.leave_approvers:
		for la in dept_doc.leave_approvers:
			allowed_ids.append(la.approver)
	if dept_doc.expense_approvers:
		for expa in dept_doc.expense_approvers:
			allowed_ids.append(expa.approver)
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
						allowed_ids.extend([emp_doc.user_id])
	if customer_doc.customer_login_id:
		allowed_ids.extend([customer_doc.customer_login_id])
	if customer_doc.default_sales_partner:
		s_partner = frappe.get_doc("Sales Partner", customer_doc.default_sales_partner)
		if s_partner.user:
			user = frappe.get_doc("User", s_partner.user)
			if user.enabled == 1:
				allowed_ids.extend([s_partner.user])
	return allowed_ids

def create_account_perms(acc_doc, user_dict):
	allowed_ids = get_account_allowed_ids(acc_doc.name, user_dict)
	if allowed_ids:
		for user in allowed_ids:
			role_list = get_user_roles(user)
			role_in_settings, apply_to_all_doctypes, applicable_for = \
				check_role(role_list, doctype=acc_doc.doctype, \
				apply_to_all_doctypes="None")
			if role_in_settings == 1:
				create_new_user_perm(user=user, allow=acc_doc.doctype, \
					for_value=acc_doc.name, applicable_for=applicable_for, \
					apply_to_all_doctypes=apply_to_all_doctypes)
	delete_extra_account_perms(acc_doc, user_dict)

def delete_extra_account_perms(acc_doc, user_dict):
	allowed_ids = get_account_allowed_ids(acc_doc.name, user_dict)
	acc_perm_list = get_permission(for_value=acc_doc.name)
	settings_list = get_user_perm_settings(allow="Account", \
		apply_to_all_values="None", apply_to_all_doctypes="None", \
		apply_to_all_roles="None")
	applicable_for_dt_list = []
	for settings in settings_list:
		if settings[4] != 1:
			applicable_for_dt_list.append(settings[3])

	for perm in acc_perm_list:
		if perm[4] not in applicable_for_dt_list:
			delete_permission(name=perm[0])
		if perm[3] in allowed_ids:
			#Check if the user role is there and if not delete
			role_list = get_user_roles(perm[3])
			role_in_settings, apply_to_all_doctypes, applicable_for = \
				check_role(role_list, doctype=acc_doc.doctype, \
				apply_to_all_doctypes="None")
			if role_in_settings != 1:
				delete_permission(name=perm[0])
		else:
			delete_permission(name=perm[0])

def check_account_perm(acc_doc):
	if acc_doc.users:
		create_account_perms(acc_doc, acc_doc.users)
		if acc_doc.is_group	== 1:
			child_acc_list = get_child_acc_list(acc_doc.name)
			for child_acc in child_acc_list:
				child_acc_doc = frappe.get_doc("Account", child_acc[0])
				create_account_perms(child_acc_doc, child_acc_doc.users)
	else:
		delete_extra_account_perms(acc_doc, acc_doc.users)

def check_all_account_perm():
	acc_list = frappe.db.sql("""SELECT name
		FROM `tabAccount`""", as_list=1)
	for acc in acc_list:
		acc_doc = frappe.get_doc("Account", acc[0])
		if acc_doc.users:
			create_account_perms(acc_doc, acc_doc.users)
		delete_extra_account_perms(acc_doc, acc_doc.users)

def copy_users_to_child_accounts(acc_doc):
	if acc_doc.is_group == 1:
		child_acc_list = get_child_acc_list(acc_doc.name)
		if child_acc_list:
			for child_acc in child_acc_list:
				child_acc_doc = frappe.get_doc("Account", child_acc[0])
				copy_grp_user_to_child(acc_doc, child_acc_doc)

def copy_grp_user_to_child(grp_acc_doc, child_acc_doc):
	child_acc_doc.users = []
	user_list = []
	if grp_acc_doc.users:
		for row in grp_acc_doc.users:
			user_dict = {}
			user_dict.setdefault("approver", row.approver)
			user_list.append(user_dict)
		for i in user_list:
			child_acc_doc.append("users", i)
	else:
		child_acc_doc.users = []
	child_acc_doc.save()

def get_child_acc_list(account_name):
	acc_doc = frappe.get_doc("Account", account_name)
	query = """SELECT name FROM `tabAccount` 
		WHERE lft > %s AND rgt < %s"""%(acc_doc.lft, acc_doc.rgt)
	child_acc_list = frappe.db.sql(query, as_list=1)
	return child_acc_list

def get_account_allowed_ids(account_name, user_dict):
	allowed_ids=[]
	acc_doc = frappe.get_doc("Account", account_name)
	if user_dict:
		for row in user_dict:
			allowed_ids.extend([row.approver])
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
	apply_to_all_values=None, apply_to_all_doctypes=None):
	#This would check if the user permission needs to be created or not.
	conditions = ""
	if allow:
		conditions += " AND allow_doctype = '%s'"%(allow)
	if role:
		conditions += " AND role = '%s'"%(role)
	
	if apply_to_all_roles == 1:
		conditions += " AND apply_to_all_roles = 1"
	elif apply_to_all_roles == "None":
		pass
	else:
		conditions += " AND apply_to_all_roles = 0"

	if apply_to_all_values==1:
		conditions += " AND apply_to_all_values = 1"
	elif apply_to_all_values == "None":
		pass
	else:
		conditions += " AND apply_to_all_values = 0"
	
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
		role_list = get_user_roles(perm[3])
		role_in_settings, apply_to_all_doctypes, applicable_for = \
			check_role(role_list=role_list, doctype=perm[1], \
			apply_to_all_doctypes=1)
		if role_in_settings != 1:
			delete_permission(name=perm[0])
	#Remove Inactive Employee Permissions
	emp_list = get_employees(status='Left')
	for emp in emp_list:
		left_emp_list = get_permission(allow="Employee", for_value=emp[0])
		for perm in left_emp_list:
			delete_permission(name=perm[0])

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

def get_usershare_settings(document_type=None, role=None, apply_to_all_roles=None, \
	apply_to_all_values=None, document_name=None):
	#This would check if the user permission needs to be created or not.
	conditions = ""
	if document_type:
		conditions += " AND document_type = '%s'"%(document_type)
	
	if document_name:
		conditions += " AND document_name = '%s'"%(document_name)

	if role:
		conditions += " AND role = '%s'"%(role)
	
	if apply_to_all_roles == 1:
		conditions += " AND apply_to_all_roles = 1"
	elif apply_to_all_roles == "None":
		pass
	else:
		conditions += " AND apply_to_all_roles = 0"

	if apply_to_all_values==1:
		conditions += " AND apply_to_all_values = 1"
	elif apply_to_all_values == "None":
		pass
	else:
		conditions += " AND apply_to_all_values = 0"

	query = """SELECT name, role, apply_to_all_roles, document_type, document_name, 
		apply_to_all_values, read_access, write_access, share_access, notify_by_email
		FROM `tabUser Share Rules` WHERE parent = 'User Share Settings' 
		AND parentfield = 'rules' %s"""\
		%(conditions)
	settings_dict = frappe.db.sql(query, as_dict=1)
	return settings_dict

def check_role_usershare(role_list, doctype):
	role_in_settings = 0
	settings_dict = get_usershare_settings(document_type=doctype, \
		apply_to_all_values=1)
	if settings_dict:
		for set_dict in settings_dict:
			read_access = set_dict.read_access
			write_access = set_dict.write_access
			share_access = set_dict.share_access
			notify_by_email = set_dict.notify_by_email
			document_type = set_dict.document_type
			for role in role_list:
				if role[0] == set_dict.role:
					role_in_settings = 1
	else:
		role_in_settings = 0
		read_access = 0
		write_access = 0
		share_access = 0
		notify_by_email = 0

	return role_in_settings, write_access,share_access, notify_by_email

def get_shared(name=None, user=None, document_type=None, document_name=None):
	conditions = ''
	if name:
		conditions += " AND name = '%s'"%(name)
	if user:
		conditions += " AND user = '%s'"%(user)
	if document_type:
		conditions += " AND share_doctype = '%s'"%(document_type)
	if document_name:
		conditions += " AND share_name = '%s'"%(document_name)

	query = """SELECT name, user, share_doctype, share_name, `read`, `write`,
		`share`, `everyone`, notify_by_email
		FROM `tabDocShare` WHERE docstatus = 0 %s"""%(conditions)
	share_dict = frappe.db.sql(query , as_dict=1)
	return share_dict