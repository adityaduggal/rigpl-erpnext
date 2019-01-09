# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

'''
1. Check if User is Active, if yes then get all default values for User
'''
from __future__ import unicode_literals
import frappe
from rigpl_erpnext.utils.rigpl_perm import *

def create_defaults():
	user_list = get_users(active=1)
	for user in user_list:
		print("Checking for Defaults for User:" + user[0])
		role_list = get_user_roles(user[0])
		for role in role_list:
			all_role_settings = get_user_perm_settings(apply_to_all_roles=1)
			for setting in all_role_settings:
				create_new_user_perm(allow=setting[1], \
					for_value=setting[2], user=user[0], \
					applicable_for=setting[3], \
					apply_to_all_doctypes=setting[4])

			default_value_settings = get_user_perm_settings(role=role[0], \
				apply_to_all_doctypes="None")
			for setting in default_value_settings:
				create_new_user_perm(allow=setting[1], \
					for_value=setting[2], user=user[0], \
					applicable_for=setting[3], \
					apply_to_all_doctypes=setting[4])