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
			att_time[i] = datetime.strptime(att_time[i], '%Y-%m-%d %H:%M:%S')
			att_time[i+1] = datetime.strptime(att_time[i+1], '%Y-%m-%d %H:%M:%S')
			diff = (att_time[i+1] - att_time[i])
			
			#Checks if the two entries are apart by at least 10 mins
			if diff < timedelta(minutes=10):
				frappe.msgprint('{0}{1}'.format("Difference between 2 times cannot be less than 10 mins, Check line #", i+2), raise_exception=1)
		elif att_tt[i] == "Out Time":
			if att_tt[i+1] <> "In Time":
				frappe.msgprint('{0}{1}'.format("Out Time should be followed by In Time check line #", i+2),raise_exception=1)
	
	#Check if there are at least 4 Punch Data in the Time Table
	if doc.attendance_time:
		for att in doc.attendance_time:
			if len(doc.attendance_time) <= 1:
				frappe.msgprint("Atleast 2 times are needed", raise_exception = 1)
	
	#Error if there is NO DATA in the Time Table
	else:
		frappe.msgprint("Time details are mandatory", raise_exception = 1)
	
