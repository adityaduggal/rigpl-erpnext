# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def execute():
	dt_list = ["Employee", "Leave Application", "Salary Slip", "Expense Claim", "Attendance"]
	for dt in dt_list:
		print("Checking Department for all " + dt)
		mysql_table = 'tab' + dt
		list_of_doc = frappe.db.sql("""SELECT name FROM `%s`
			WHERE department IS NULL"""%(mysql_table), as_list=1)
		for docs in list_of_doc:
			frappe.db.set_value(dt, docs[0], "department", "All Departments")
			print("Updated Department for " + dt + " " + docs[0] + " to All Departments")