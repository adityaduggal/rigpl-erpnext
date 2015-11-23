# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import cstr
from datetime import datetime, timedelta

def validate(doc,method):
	#Check if the employee is Active for the Dates
	emp = frappe.get_doc("Employee", doc.employee)
	if emp.status == "Left":
		frappe.msgprint("hello")
		#if isinstance(doc.att_date, basestring):
		#	doc.att_date = datetime.strptime(doc.att_date, '%Y-%m-%d').date()
		if emp.relieving_date < doc.att_date:
			frappe.msgprint('{0}{1}{2}'.format("Can't create attendance for ",  emp.employee_name, " as he/she has already LEFT on this Date"), raise_exception = 1)

	att_tt = []
	att_time = []

	for d in doc.attendance_time:
		att_tt.append(cstr(d.time_type))
		att_time.append(cstr(d.date_time))
		
	for i in range(len(att_tt)-1):
		if att_tt[i] == "In Time":
			if att_tt[i+1] <> "Out Time":
				frappe.msgprint('{0}{1}'.format("In Time should be followed by Out Time check line #", i+2),raise_exception=1)
			diff = time_diff(att_time[i], att_time[i+1])
			diff_allowed(diff, i)

		elif att_tt[i] == "Out Time":
			if att_tt[i+1] <> "In Time":
				frappe.msgprint('{0}{1}'.format("Out Time should be followed by In Time check line #", i+2),raise_exception=1)
			
			diff = time_diff(att_time[i], att_time[i+1])
			diff_allowed(diff,i)
	
	#Check if there is an even number of punch data
	if doc.attendance_time:
		for att in doc.attendance_time:
			if (len(doc.attendance_time)) % 2 <> 0:
				frappe.msgprint("Time Data has to be multiple of 2", raise_exception = 1)

				
#Function to find the difference between 2 times
def time_diff (time1, time2):
	time1 = datetime.strptime(time1, '%Y-%m-%d %H:%M:%S')
	time2 = datetime.strptime(time2, '%Y-%m-%d %H:%M:%S')
	diff = time2 - time1
	return diff

#Function to define the minimum and max difference allowed between times
def diff_allowed(time, i):
	if time < timedelta(minutes=10):
		frappe.msgprint('{0}{1}'.format("Difference between 2 times cannot be less than 10 mins, Check line #", i+2), raise_exception=1)
	
	if time > timedelta(hours = 18):
		frappe.msgprint('{0}{1}'.format("Difference between 2 times cannot be greater than 18 hrs, Check line #", i+2), raise_exception=1)