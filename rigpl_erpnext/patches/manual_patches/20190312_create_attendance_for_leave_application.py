# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import add_days

def execute():
	leave_app_list = frappe.db.sql("""SELECT name FROM `tabLeave Application` 
		WHERE docstatus = 1 AND status = 'Approved'
		ORDER BY name ASC""", as_list=1)
	for leave_app in leave_app_list:
		print("Checking for Leave Application " + leave_app[0])
		la_doc = frappe.get_doc("Leave Application", leave_app[0])
		att_list = frappe.db.sql("""SELECT name FROM `tabAttendance` 
			WHERE docstatus = 1 AND employee ='%s' AND attendance_date BETWEEN '%s' AND '%s'"""%(la_doc.employee, \
				la_doc.from_date, la_doc.to_date), as_list=1)
		if att_list:
			for att in att_list:
				status = frappe.db.get_value("Attendance", att[0], "status")
				if status != 'On Leave':
					if status == 'Half Day':
						if la_doc.total_leave_days != 0.5:
							print('Half Day Error for ' + att[0] + ' and Leave App ' + leave_app[0])
					else:
						print('Error for ' + att[0] + ' and Leave App ' + leave_app[0])
		else:
			leave_days = la_doc.total_leave_days
			for lday in range(int(leave_days)):
				shift_request = frappe.db.sql("""SELECT name FROM `tabShift Assignment` 
					WHERE employee = '%s' AND docstatus = 1 AND `date` = '%s'"""%\
					(la_doc.employee, add_days(la_doc.from_date, lday)),as_list=1)

				if not shift_request:
					new_sr = frappe.new_doc("Shift Assignment")
					new_sr.employee = la_doc.employee
					new_sr.company = la_doc.company
					new_sr.shift_type = 'General Shift G-Shift With In and Out'
					new_sr.date = add_days(la_doc.from_date, lday)
					new_sr.docstatus = 1
					new_sr.insert()
					print("Added Shift Request " + str(new_sr.name) + " for Employee " + \
						la_doc.employee + " with Name: " + str(la_doc.employee_name))
					frappe.db.commit()

				new_att = frappe.new_doc("Attendance")
				new_att.docstatus = 1
				new_att.employee = la_doc.employee
				new_att.attendance_date = add_days(la_doc.from_date, lday)
				if la_doc.total_leave_days == int(la_doc.total_leave_days):
					new_att.status = 'On Leave'
				new_att.company = la_doc.company
				new_att.department = la_doc.department
				new_att.insert()
				print('Added Attendance for Employee ' + la_doc.employee + ' Name: ' + str(la_doc.employee_name) + ' for Leave Application ' + la_doc.name)
			frappe.db.commit()