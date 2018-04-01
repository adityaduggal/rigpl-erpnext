# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

'''
1. Check if User is Active, if not DELETE all permissions.
2. Check if User has any permission in Customer if so then add Address and Contact linked with Customer
3. Check if User has any EXTRA contacts and Address and delete and also CONTACTS
'''
from __future__ import unicode_literals
import frappe
from rigpl_erpnext.rigpl_erpnext.validations.lead import \
	create_new_user_perm, delete_unused_perm, find_total_perms, \
	check_system_manager, get_dl_parent

def check_permission_exist():
	inactive_users = get_users(active=0)
	for user in inactive_users:
		delete_permission(user[0])
	active_users = get_users(active=1)
	for user in active_users:
		check_sys = check_system_manager(user[0])
		#Check permission for Company if does not exists create
		#Check permission for Customers if does not exists create
		#Check permission for Address if does not exists then check in deleted_docs if yes restore, else create
		#Check permission for Contact if does not exists then check in deleted_docs if yes restore
		if check_sys == 1:
			print("User: " + user[0] + " is a System Manager")
			delete_permission(user[0])
		else:
			#Check if user in LEAD and if so then check perm or else add perm for lead and address
			lead_list = get_user_lead(user[0])
			if lead_list:
				for lead in lead_list:
					lead_perm = get_permission(user[0], allow='Lead', for_value=lead[0])
					if not lead_perm:
						create_new_user_perm('Lead', lead[0], user[0])
						print('Added Permission for Lead: ' + lead[0] + " for User: " + user[0])

					add_list = get_dl_parent(dt='Address', linked_dt='Lead', linked_dn= lead[0])
					if add_list:
						for address in add_list:
							#find existing permission and if not create perm
							add_perm = get_permission(user[0], allow='Address', for_value=address[0])
							if not add_perm:
								create_new_user_perm('Address', address[0], user[0])
								print('Added Permission for Address: ' + address[0] + " for User: " + user[0])
			#Check If user linked to Employee if yes then check if linked to Sales Person
			#then check if Sales Person is linked to customer and then add customer
			#then check corresponding Contact and Address and then add to permissions
			emp = get_user_emp(user[0])
			if emp:
				s_person = get_sales_person(emp[0][0])
			else:
				s_person = []

			if s_person:
				cust_list = get_cust_from_sperson(s_person[0][0], 'Customer')
			else:
				cust_list = []

			if cust_list:
				for customer in cust_list:
					#find existing permission and if not create perm
					cust_perm = get_permission(user[0], allow='Customer', for_value=customer[0])
					if not cust_perm:
						create_new_user_perm('Customer', customer[0], user[0])

					con_list = get_dl_parent(dt='Contact', linked_dt='Customer', linked_dn= customer[0])
					if con_list:
						for contact in con_list:
							#find existing permission and if not create perm
							cont_perm = get_permission(user[0], allow='Contact', for_value=contact[0])
							if not cont_perm:
								create_new_user_perm('Contact', contact[0], user[0])
					add_list = get_dl_parent(dt='Address', linked_dt='Customer', linked_dn= customer[0])
					if add_list:
						for address in add_list:
							#find existing permission and if not create perm
							add_perm = get_permission(user[0], allow='Address', for_value=address[0])
							if not add_perm:
								create_new_user_perm('Address', address[0], user[0])
		print("Completed Adding Permissions for User: " + user[0])
	version_delete = [['Bin', 'creator=None', 'creation=None'], \
		['Carrier Tracking', 'creator= "Administrator"', 'creation=today()'], \
		['Stock Ledger Entry', 'creator=None', 'creation=None'], \
		['GL Entry', 'creator=None', 'creation=None']]
	for version in version_delete:
		delete_version(version[0], version[1], version[2])
	delete_docs = ['User Permission', 'Error Log', 'Email Group Member', 'Version']
	for d in delete_docs:
		delete_from_deleted_doc(d)

def delete_version(document, creator=None, creation=None):
	condition = ''
	if creator:
		condition = " AND owner = '%s'"

	if creation:
		condition = " AND creation <= DATE_SUB(NOW(), INTERVAL 5 DAY)"

	version_list = frappe.db.sql("""SELECT name FROM `tabVersion` 
		WHERE ref_doctype = '%s' %s""" %(document, condition), as_list=1)
	if version_list:
		for version in version_list:
			frappe.delete_doc_if_exists("Version", version[0])
			frappe.db.commit()
			print("Deleted Version: " + version[0])

def delete_from_deleted_doc(document):
	del_doc_list = frappe.db.sql("""SELECT name FROM `tabDeleted Document` 
		WHERE deleted_doctype = '%s'"""%(document), as_list=1)
	if del_doc_list:
		for del_doc in del_doc_list:
			frappe.delete_doc_if_exists("Deleted Document", del_doc[0])
			frappe.db.commit()
			print("Deleted " + del_doc[0])

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

def get_permission(user, allow=None, for_value=None, deleted=None):
	condition = ''
	if allow:
		condition += " AND allow = '%s'"%(allow)
	if for_value:
		condition += " AND for_value = '%s'"%(for_value)
	query = """SELECT name, allow, for_value, user
		FROM `tabUser Permission` WHERE user = '%s' %s"""%(user, condition)
	permission_list = frappe.db.sql(query , as_list=1)

	return permission_list


def delete_permission(user, allow=None, for_value=None):
	permission_list = get_permission(user, allow=allow, for_value=for_value)
	for perm in permission_list:
		frappe.delete_doc_if_exists("User Permission", perm[0])
		print ('Deleted User Permission: ' + perm[0] + ' for User: ' + perm[3])
		frappe.db.commit()

def restore_deleted_permission(name):
	restore(name)