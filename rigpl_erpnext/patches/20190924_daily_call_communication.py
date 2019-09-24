# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def execute():
	comm_list = frappe.db.sql("""SELECT name, owner, sender FROM `tabCommunication` 
		WHERE communication_subtype = 'Sales Related' AND sender IS NULL""", as_dict=1)
	for comm in comm_list:
		frappe.db.set_value('Communication', comm.name, 'sender', comm.owner)
		print('Update Communication # ' + comm.name)
	print(len(comm_list))