# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import nowdate, time_diff_in_hours, now_datetime
import html2text

def daily():
	today = nowdate()
	now = now_datetime()
	#First Check for Communications which can be used for making TODO
	#only communication_type == "Communication" and communication_subtype == "Sales Related" 
	#and next_action_date IS NOT NULL
	comm = frappe.db.sql ("""SELECT name FROM `tabCommunication` 
		WHERE communication_type = 'Communication' AND follow_up = 1 
		AND DATE(next_action_date) <= CURDATE()""", as_list= 1)
	
	for i in comm:
		#Check if the communication is already in TODO for the user and Open.
		#TODO Assigned by == Owner of the Communication
		#TODO Owner  == User of Communication
		comm = frappe.get_doc("Communication", i[0])
		todo = frappe.db.sql("""SELECT name FROM `tabToDo` 
			WHERE reference_type = 'Communication' AND reference_name = '%s' AND 
			assigned_by = '%s' AND owner = '%s' """ %(i[0], comm.owner, comm.user), as_list=1)
		
		if todo:
			tododoc = frappe.get_doc("ToDo", todo[0][0])
			if tododoc.status == "Open":
				send_reminder = check_follow_up_time(comm.next_action_date, now)
				if send_reminder == 1:
					send_follow_up_email(comm.user, comm.modified_by, comm.subject, \
						comm.content, comm.reference_doctype, comm.reference_name)
			else:
				frappe.db.set_value("ToDo", todo[0][0], "status", "Open")
				send_reminder = check_follow_up_time(comm.next_action_date, now)
				if send_reminder == 1:
					send_follow_up_email(comm.user, comm.modified_by, comm.subject, \
						comm.content, comm.reference_doctype, comm.reference_name)
		else:
			#Create TODO
			todo = frappe.new_doc("ToDo")
			todo.status = "Open"
			todo.priority = "High"
			todo.date = comm.next_action_date.date()
			todo.owner = comm.user
			todo.reference_type = "Communication"
			todo.reference_name = comm.name
			todo.type = comm.communication_subtype
			todo.assigned_by = comm.owner
			todo.description = comm.subject + "\n" + html2text.html2text(comm.content)[0:100] \
				+ "\n" + comm.reference_doctype + " " + comm.reference_name
			todo.insert()
			send_follow_up_email(comm.user, comm.owner, comm.subject, \
				comm.content, comm.reference_doctype, comm.reference_name)

def check_follow_up_time(time, now):
	send_reminder = 0
	if 1 < (time_diff_in_hours(time, now)) < 2:
		send_reminder = 1
	return send_reminder

def send_follow_up_email(user, sender, subject, content, ref_doc, ref_name):
	frappe.sendmail(recipients=user,
		sender=sender,
		subject="Follow Up for: " + subject, 
		content= content + "\n"  + ref_doc + " " + ref_name)