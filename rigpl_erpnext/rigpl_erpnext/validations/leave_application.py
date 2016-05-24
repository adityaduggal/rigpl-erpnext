# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc,method):
	#Check if there is any attendance for an employee
	att = frappe.db.sql("""SELECT name FROM `tabAttendance` 
		WHERE docstatus = 1 AND employee = '%s' AND att_date >= '%s' AND
		att_date <= '%s'"""%(doc.employee, doc.from_date, doc.to_date), as_list=1)
	if att:
		frappe.throw(("Employee: {0} already has attendance between {1} and {2}").format(doc.employee_name, doc.from_date, doc.to_date))