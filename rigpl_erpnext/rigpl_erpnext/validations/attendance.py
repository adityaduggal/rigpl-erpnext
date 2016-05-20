# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import division
import frappe
from frappe import msgprint
from frappe.utils import getdate, cint, add_months, date_diff, add_days, nowdate, \
	get_datetime_str, cstr, get_datetime, time_diff, time_diff_in_seconds
from datetime import datetime, timedelta

def on_update(doc,method):
	validate(doc,method)

def validate(doc,method):
	global att_date
	att_tt = []
	att_time = []
	att_date = getdate(doc.att_date)
	if doc.status <> "Present" and doc.status <> "Half Day":
		frappe.throw(("Only Present or Half Day Attendance is Allowed Check {0}").format(doc.name))

	check_employee (doc, method)
	shft = get_shift(doc,method)
	if shft.in_out_required:
		calculate_overtime(doc,method)
	

				
#Function to check if the attendance is not for a NON-WORKING employee
def check_employee(doc, method):
	#Check if the employee is Active for the Dates
	emp = frappe.get_doc("Employee", doc.employee)
	if emp.status == "Left":
		if emp.relieving_date < att_date:
			frappe.throw(("Cannot create attendance for {0} as he/she has left on {1}").\
			format(emp.employee_name, emp.relieving_date))
	else:
		if emp.date_of_joining > att_date:
			frappe.throw(("Cannot create attendance for {0} as he/she has joined on {1}").\
			format(emp.employee_name, emp.date_of_joining))

#Function to check the shift and update the same from roster.
def get_shift(doc,method):
	query = """SELECT ro.name, ro.shift FROM `tabRoster` ro, `tabRoster Details` rod
		WHERE rod.parent = ro.name AND ro.from_date <= '%s' AND ro.to_date >= '%s' 
		AND rod.employee = '%s' """%(att_date, att_date, doc.employee)
	roster = frappe.db.sql(query, as_list=1)
	if len(roster)<1:
		frappe.throw(("No Roster defined for {0} for date {1}").format(doc.employee, att_date))
	else:
		doc.shift = roster[0][1]
	
	shft = frappe.get_doc("Shift Details", doc.shift)
	return shft

def validate_time_with_shift(doc,method):
	shft = frappe.get_doc("Shift Details", doc.shift)
	if shft.in_out_required:
		shft_hrs = shft.hours_required_per_day.seconds
		shft_rounding = shft.time_rounding.seconds
		shft_marg = shft.time_margin.seconds
		
		if shft_rounding <= 0 or shft_marg <=0:
			frappe.throw("Shift Rounding or Shift Margin cannot be Zero")
		
		if shft.in_time > shft.out_time:
			#this shows night shift
			if shft.next_day <> 1:
				#this shows night shift is starting on previous day
				shft_indate = datetime.combine(add_days(att_date, -1), datetime.min.time())
			else:
				shft_indate = datetime.combine(att_date, datetime.min.time())
		else:
			shft_indate = datetime.combine(att_date, datetime.min.time())
		
		shft_intime = shft_indate + timedelta(0, shft.in_time.seconds)
		shft_intime_max = shft_intime + timedelta(0, shft.delayed_entry_allowed_time.seconds)
		shft_intime_min = shft_intime - timedelta(0, shft.early_entry_allowed_time.seconds)
		
		if shft.lunch_out > shft.in_time:
			shft_lunchout = shft_indate + timedelta(0, shft.lunch_in.seconds)
			shft_lunchin = shft_indate + timedelta(0, shft.lunch_in.seconds)
		else:
			shft_lunchout = shft_indate + timedelta(0, 86400+shft.lunch_in.seconds)
			shft_lunchin = shft_indate + timedelta(0, 86400+shft.lunch_in.seconds)
		
		for d in doc.attendance_time:
			if d.idx == 1:
				d.date_time = get_datetime(d.date_time)
				if d.date_time >= shft_intime_min and d.date_time <= shft_intime_max:
					pass
				else:
					frappe.throw(("Time {0} in row#1 is not allowed for Shift# {1} for {2}.\
						Check early and delayed entry settings in Shift Master").\
						format(d.date_time, doc.shift, doc.name))

		return shft_intime, shft_lunchout, shft_lunchin, shft_hrs, shft_rounding, shft_marg
	
def calculate_overtime(doc,method):
	doc.overtime = 0
	tt_in = 0
	tt_out = 0
	
	shft_intime, shft_lunchout, shft_lunchin, shft_hrs, \
		shft_rounding, shft_marg = validate_time_with_shift(doc,method)
	
	pu_data = check_punch_data(doc, method)
	
	#only calculate the ot if there are any IN and OUT entries
	#if doc.attendance_time:
	for i in range(len(doc.attendance_time)-1):
		pass
	for i in range(len(pu_data)-1):
		if pu_data[i][1] == 'In Time':
			tt_in +=  time_diff_in_seconds(pu_data[i+1][2], pu_data[i][2])
		else:
			tt_out += time_diff_in_seconds(pu_data[i+1][2], pu_data[i][2])
				
	doc.overtime = ((tt_in - shft_hrs + shft_marg)- \
		((tt_in + shft_marg - shft_hrs)%shft_rounding))/3600
	
def check_punch_data(doc,method):
	
	shft_intime, shft_lunchout, shft_lunchin, shft_hrs, \
		shft_rounding, shft_marg = validate_time_with_shift(doc,method)
	pu_data = []
	
	for d in doc.attendance_time:
		if d.idx == 1 and d.time_type <> 'In Time':
			frappe.throw(("First Punch Data should be In Time for {0}").format(doc.name))
		pu_data.append([d.idx, d.time_type, d.date_time])

	for i in range(len(pu_data)-1):
		#Checks if In and Out are alternating
		if pu_data[i][1] == pu_data[i+1][1]:
			frappe.throw(("{1} should not be Followed by {1} for {2} check row # {3} & {4}").\
				format(pu_data[i][1], pu_data[i][1], doc.name, pu_data[i][0], pu_data[i+1][0]))
		#Checks if Time Data is following the minimum time difference rule in shift
		if time_diff_in_seconds(pu_data[i+1][2], pu_data[i][2]) <= shft_marg:
			frappe.throw(("Difference between 2 punch data cannot be less than \
				{0} mins check row# {1} and {2} for {3}").\
				format(shft_marg/60, pu_data[i][0], pu_data[i+1][0], doc.name))

	return pu_data
		
#Function to define the minimum and max difference allowed between times
def diff_allowed(time, i, min_in_mins, max_in_hours):
	if time < timedelta(minutes=min_in_mins):
		frappe.msgprint('{0}{1}'.format("Difference between 2 times cannot be less than 10 mins, Check line #", i+2), 
			raise_exception=1)
	
	if time > timedelta(hours = max_in_hours):
		frappe.msgprint('{0}{1}'.format("Difference between 2 times cannot be greater than 18 hrs, Check line #", i+2), 
			raise_exception=1)
