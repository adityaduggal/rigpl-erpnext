# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import nowdate

def daily(doc, method):
	today = nowdate()
	#First Check for Communications which can be used for making TODO
	#only communication_type == "Communication" and communication_subtype == "Sales Related" 
	#and next_action_date IS NOT NULL
	comm = frappe.db.sql ("""SELECT name FROM `tabCommunication` 
		WHERE communication_type = 'Communication' AND communication_subtype = 'Sales Related' 
		AND next_action_date = CURDATE()""", as_list= 1)
	
	for i in comm:
		#Check if the communication is already in TODO for the user and Open.
		#TODO Assigned by == Owner of the Communication
		#TODO Owner  == User of Communication
		comm = frappe.get_doc("Communication", i)
		todo = frappe.db.sql("""SELECT name FROM `tabToDo` 
			WHERE reference_type = 'Communication' AND reference_name = '%s' AND 
			assigned_by = '%s' AND owner = '%s' """ %(i, comm.owner, comm.next_action_by), as_list=1)
		
		if todo:
			pass
		else:
			#Create TODO
			todo = frappe.new_doc("ToDo")
			todo.status = "Open"
			todo.priority = "High"
			todo.due_date = comm.next_action_date
			todo.owner = comm.next_action_by
			todo.reference_type = "Communication"
			todo.reference_name = comm.name
			todo.type = comm.communication_subtype
			todo.assigned_by = comm.owner
			todo.description = comm.subject + "/n" + comm.content
			todo.insert()