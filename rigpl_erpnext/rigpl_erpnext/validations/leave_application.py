# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import add_days


def validate(doc,method):
	doc.deparment = frappe.get_value("Employee", doc.employee, "department")
	#Check if there is any attendance for an employee
	att = frappe.db.sql("""SELECT name FROM `tabAttendance` 
		WHERE docstatus = 1 AND employee = '%s' AND attendance_date >= '%s' AND
		attendance_date <= '%s'"""%(doc.employee, doc.from_date, doc.to_date), as_list=1)
	if att:
		frappe.throw(("Employee: {0} already has attendance between {1} and {2}").format(doc.employee_name, doc.from_date, doc.to_date))
	if doc.half_day == 1:
		frappe.throw("Half Day Leave Application is Not Allowed")

def on_submit(doc, method):
	create_attendance(doc)

def create_attendance(la_doc):
	leave_days = la_doc.total_leave_days
	for lday in range(int(leave_days)):
		new_att = frappe.new_doc("Attendance")
		new_att.docstatus = 1
		new_att.employee = la_doc.employee
		new_att.employee_name = la_doc.employee_name
		new_att.attendance_date = add_days(la_doc.from_date, lday)
		if la_doc.total_leave_days == int(la_doc.total_leave_days):
			new_att.status = 'On Leave'
		new_att.company = la_doc.company
		new_att.department = la_doc.department
		new_att.flags.ignore_validate = True
		new_att.insert(ignore_permissions=True)
		frappe.msgprint("Created Attendance for Employee {}".format(la_doc.employee))