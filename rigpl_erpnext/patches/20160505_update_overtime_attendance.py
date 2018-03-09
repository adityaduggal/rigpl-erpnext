# -*- coding: utf-8 -*-
import frappe
from frappe.utils import time_diff_in_seconds

def execute():
	att = frappe.db.sql("""SELECT at.name, at.att_date, at.employee, at.employee_name, at.overtime,
		at.shift
		FROM `tabAttendance` at, `tabShift Details` sh
		WHERE at.docstatus = 1 AND sh.in_out_required = 1 AND at.shift = sh.name
		ORDER BY at.name""", as_list=1)
				
	for i in att:
		att = frappe.get_doc("Attendance", i[0])
		shft = frappe.get_doc("Shift Details", i[5])
		pu_data = []
		overtime = 0
		tt_in = 0
		tt_out = 0
		shft_hrs = shft.hours_required_per_day.seconds
		shft_marg = shft.time_margin.seconds
		shft_rounding = shft.time_rounding.seconds
		
		for d in att.attendance_time:
			pu_data.append([d.idx, d.time_type, d.date_time])
		
		#only calculate the ot if there are any IN and OUT entries
		for j in range(len(pu_data)-1):
			if pu_data[j][1] == 'In Time':
				tt_in +=  time_diff_in_seconds(pu_data[j+1][2], pu_data[j][2])
			else:
				tt_out += time_diff_in_seconds(pu_data[j+1][2], pu_data[j][2])
					
		overtime = ((tt_in - shft_hrs + shft_marg)- \
			((tt_in + shft_marg - shft_hrs)%shft_rounding))/3600
		
		frappe.db.set_value("Attendance", i[0], 'overtime', overtime)
		
		print ("Attendance Updated " + i[0] + " for date:" + i[1] + " employee: " + i[3] + " New OT=" + overtime)