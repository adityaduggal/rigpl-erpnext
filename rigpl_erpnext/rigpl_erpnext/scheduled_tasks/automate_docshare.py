# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from rigpl_erpnext.utils.rigpl_perm import *
from rigpl_erpnext.rigpl_erpnext.validations.lead import lead_docshare, lead_quote_share, lead_address_share
from frappe.utils.background_jobs import enqueue
from time import time


def enqueue_docshare():
	enqueue(execute, queue="long", timeout=1500)


def execute():
	st_time = time()
	inactive_users = get_users(active=0)
	for user in inactive_users:
		delete_docshare(user=user[0])
	frappe.db.commit()
	active_users = get_users(active=1)
	lead_list = frappe.db.sql("""SELECT name FROM `tabLead` 
		ORDER BY creation DESC""", as_list=1)
	commit_chk = 0
	for lead in lead_list:
		lead_doc = frappe.get_doc("Lead", lead[0])
		print("Checking For Lead " + lead[0])
		lead_docshare(lead_doc)
		lead_quote_share(lead_doc)
		lead_address_share(lead_doc)
		commit_chk += 1
		if commit_chk%100 == 0:
			frappe.db.commit()
	tot_time = int(time() - st_time)
	print(f"Total Time Taken {tot_time} seconds")