# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import division
import frappe
from frappe import msgprint
from frappe.utils import cstr
from datetime import datetime, timedelta

def validate(doc,method):
	#Check if the employee is Active for the Dates
	emp = frappe.get_doc("Employee", doc.employee)
	if emp.status == "Left":
		doc.att_date = datetime.strptime(doc.att_date, '%Y-%m-%d').date()
		if emp.relieving_date < doc.att_date:
			frappe.msgprint('{0}{1}{2}'.format("Can't create attendance for ",  emp.employee_name, " as he/she has already LEFT on this Date"), raise_exception = 1)

	att_tt = []
	att_time = []
	att_date = datetime.strptime(doc.att_date, '%Y-%m-%d').date()

	for d in doc.attendance_time:
		att_tt.append(cstr(d.time_type))
		att_time.append(cstr(d.date_time))
		
	for i in range(len(att_tt)-1):
		if att_tt[i] == "In Time":
			#Checks the first Punch Data is within the Same date as that of the Attendance
			#Also checks if the first punch data is within the permissible limits of SHIFT Time
			if i < 1:
				attendance = datetime.strptime(att_time[i], '%Y-%m-%d %H:%M:%S').date()
				time = datetime.strptime(att_time[i], '%Y-%m-%d %H:%M:%S').time()
				allowed_hrs =frappe.db.get_value("Shift Details", doc.shift ,"delayed_entry_allowed_time")
				allowed_in_time = frappe.db.get_value("Shift Details", doc.shift ,"in_time")
				#time_check = time - allowed_in_time
				check = att_date - attendance
				
				frappe.msgprint(allowed_in_time)
				
				if check > timedelta(days=0) or check < timedelta(days = 0):
					frappe.msgprint("Attendance date and Attendance Time Data are not in same date", raise_exception=1)
			if att_tt[i+1] <> "Out Time":
				frappe.msgprint('{0}{1}'.format("In Time should be followed by Out Time check line #", i+2),raise_exception=1)
			diff = time_diff(att_time[i], att_time[i+1])
			diff_allowed(diff, i,10,18)

		elif att_tt[i] == "Out Time":
			if i == 0:
				#Check the first punch data should be IN TIME Only
				frappe.msgprint("First Punch Data should be IN TIME Only", raise_exception = 1)
			if att_tt[i+1] <> "In Time":
				frappe.msgprint('{0}{1}'.format("Out Time should be followed by In Time check line #", i+2),raise_exception=1)
			
			diff = time_diff(att_time[i], att_time[i+1])
			diff_allowed(diff,i,10,18)
	
	#Check if there is an even number of punch data
	if doc.attendance_time:
		for att in doc.attendance_time:
			if (len(doc.attendance_time)) % 2 <> 0:
				frappe.msgprint("Time Data has to be multiple of 2", raise_exception = 1)
				
	
	#Calculation of Overtime based on Shift and its Rules
	doc.overtime = 0
	tt_in = 0
	tt_out = 0
	hrs_needed =frappe.db.get_value("Shift Details", doc.shift ,"hours_required_per_day").seconds/3600
	round = frappe.db.get_value("Shift Details", doc.shift ,"time_rounding").seconds/3600
	
	for i in range(len(att_tt)-1):
		if att_tt[i] == "In Time":
			tt_in = tt_in + (time_diff(att_time[i], att_time[i+1]).seconds)/3600
		else:
			tt_out = tt_out + (time_diff(att_time[i], att_time[i+1]).seconds)/3600
		doc.overtime = (tt_in - hrs_needed)- ((tt_in - hrs_needed)%round)
				
#Function to find the difference between 2 times
def time_diff (time1, time2):
	time1 = datetime.strptime(time1, '%Y-%m-%d %H:%M:%S')
	time2 = datetime.strptime(time2, '%Y-%m-%d %H:%M:%S')
	diff = time2 - time1
	return diff

#Function to define the minimum and max difference allowed between times
def diff_allowed(time, i, min_in_mins, max_in_hours):
	if time < timedelta(minutes=min_in_mins):
		frappe.msgprint('{0}{1}'.format("Difference between 2 times cannot be less than 10 mins, Check line #", i+2), raise_exception=1)
	
	if time > timedelta(hours = max_in_hours):
		frappe.msgprint('{0}{1}'.format("Difference between 2 times cannot be greater than 18 hrs, Check line #", i+2), raise_exception=1)