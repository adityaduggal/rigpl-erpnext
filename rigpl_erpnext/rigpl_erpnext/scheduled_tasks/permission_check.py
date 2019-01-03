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
from rigpl_erpnext.utils.rigpl_perm import *

def check_permission_exist():
	clean_dynamic_link_table()
	clean_sales_team_table()
	#'''
	inactive_users = get_users(active=0)
	for user in inactive_users:
		delete_permission(user=user[0])
	active_users = get_users(active=1)
	for user in active_users:
		print ("Checking for User " + user[0])
		check_sys = check_system_manager(user=user[0])
		#Check permission for Company if does not exists create
		#Check permission for Customers if does not exists create
		#Check permission for Address if does not exists then check in deleted_docs if yes restore, else create
		#Check permission for Contact if does not exists then check in deleted_docs if yes restore
		if check_sys == 1:
			print("User: " + user[0] + " is a System Manager")
			delete_permission(user[0])
		else:
			#Get User Roles
			role_list = get_user_roles(user[0])
			all_role_settings = get_user_perm_settings(apply_to_all_roles=1, apply_to_all_doctypes=1)
			for setting in all_role_settings:
				#print(setting)
				create_new_user_perm(allow=setting[1], \
					for_value=setting[2], user=user[0], \
					applicable_for=setting[3], \
					apply_to_all_doctypes=setting[4])
		
			#Check if user in LEAD and if so then check perm or else add perm 
			#for lead and address
			#'''
			role_in_settings, apply_to_all_doctypes, applicable_for = \
				check_role(role_list, doctype="Lead")
			if role_in_settings == 1:
				lead_list = get_user_lead(user[0])
				if lead_list:
					for lead in lead_list:
						lead_perm = get_permission(user=user[0], allow='Lead', \
							for_value=lead[0], applicable_for=applicable_for, \
							apply_to_all_doctypes=apply_to_all_doctypes)
						if not lead_perm:
							create_new_user_perm(allow='Lead', \
								for_value=lead[0], user=user[0], \
								applicable_for=applicable_for, \
								apply_to_all_doctypes=apply_to_all_doctypes)
							print('Added Permission for Lead: ' + lead[0] + \
								" for User: " + user[0])

						add_list = get_dl_parent(dt='Address', linked_dt='Lead', \
							linked_dn= lead[0])
						role_in_settings, apply_to_all_doctypes, applicable_for = \
							check_role(role_list, doctype="Address")
						if role_in_settings == 1:
							if add_list:
								for address in add_list:
									#find existing permission and if not create perm
									add_perm = get_permission(user=user[0], \
										allow='Address', for_value=address[0], \
										applicable_for=applicable_for, \
										apply_to_all_doctypes=apply_to_all_doctypes)
									if not add_perm:
										create_new_user_perm(allow='Address', \
											for_value=address[0], user=user[0], \
											applicable_for=applicable_for, \
											apply_to_all_doctypes=apply_to_all_doctypes)
										print('Added Permission for Address: ' + \
											address[0] + " for User: " + user[0])
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
				role_in_settings, apply_to_all_doctypes, applicable_for = \
					check_role(role_list, doctype="Customer")
				if role_in_settings == 1:
					if cust_list:
						for customer in cust_list:
							#find existing permission and if not create perm
							cust_perm = get_permission(user=user[0], allow='Customer', \
								for_value=customer[0], applicable_for=applicable_for, \
								apply_to_all_doctypes=apply_to_all_doctypes)
							if not cust_perm:
								create_new_user_perm(user=user[0], allow='Customer', \
								for_value=customer[0], applicable_for=applicable_for, \
								apply_to_all_doctypes=apply_to_all_doctypes)

							con_list = get_dl_parent(dt='Contact', linked_dt='Customer', \
								linked_dn= customer[0])
							role_in_settings, apply_to_all_doctypes, applicable_for = \
								check_role(role_list, doctype="Contact")
							if role_in_settings == 1:
								if con_list:
									for contact in con_list:
										#find existing permission and if not create perm
										cont_perm = get_permission(user=user[0], allow='Contact', \
											for_value=contact[0], applicable_for=applicable_for, \
											apply_to_all_doctypes=apply_to_all_doctypes)
										if not cont_perm:
											create_new_user_perm(allow='Contact', \
												for_value=contact[0], user=user[0], \
												applicable_for=applicable_for, \
												apply_to_all_doctypes=apply_to_all_doctypes)
							add_list = get_dl_parent(dt='Address', linked_dt='Customer', \
								linked_dn= customer[0])
							role_in_settings, apply_to_all_doctypes, applicable_for = \
								check_role(role_list, doctype="Address")
							if role_in_settings == 1:
								if add_list:
									for address in add_list:
										#find existing permission and if not create perm
										add_perm = get_permission(user=user[0], allow='Address', \
											for_value=address[0], applicable_for=applicable_for, \
											apply_to_all_doctypes=apply_to_all_doctypes)
										if not add_perm:
											create_new_user_perm(allow='Address', \
												for_value=address[0], user=user[0], \
												applicable_for=applicable_for, \
												apply_to_all_doctypes=apply_to_all_doctypes)
											#'''
			#Check if the user is linked to the Employee and add user permission for the Employee
			role_in_settings, apply_to_all_doctypes, applicable_for = \
				check_role(role_list, doctype="Employee")
			if role_in_settings == 1:
				emp_list = get_employees(status='Active')
				for emp in emp_list:
					allowed_ids = get_employees_allowed_ids(emp[0])
					if allowed_ids:
						if user[0] in allowed_ids:
							create_new_user_perm(allow="Employee", user=user[0], \
								for_value=emp[0], apply_to_all_doctypes=apply_to_all_doctypes, \
								applicable_for=applicable_for)

		print("Completed Adding Permissions for User: " + user[0])
		#'''
	delete_extra_perms()
	version_delete = [['Bin', '', ''], \
		['Carrier Tracking', 'Administrator', '0'], \
		['Item', 'Administrator', '0'], \
		['Stock Ledger Entry', '', ''], \
		['GL Entry', '', '']]
	for version in version_delete:
		delete_version(version[0], version[1], version[2])
	delete_docs = ['User Permission', 'Error Log', 'Email Group Member', 'Version']
	for d in delete_docs:
		delete_from_deleted_doc(d)
