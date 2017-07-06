# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe, erpnext
from frappe.utils.fixtures import sync_fixtures

sync_fixtures()
def execute():
	'''
	This patch would add the From Date and To Date to the Child table of Roster
	'''
	rosters = frappe.db.sql("""SELECT name FROM `tabRoster` 
		WHERE docstatus = 0""", as_list=1)
	count = 0
	for rost in rosters:
		roster_doc = frappe.get_doc("Roster", rost[0])
		count += 1
		count_emp = 0
		for emp in roster_doc.employees:
			count_emp += 1
			emp_doc = frappe.get_doc("Employee", emp.employee)
			relieving_date = emp_doc.relieving_date
			frappe.db.set_value('Roster Details', emp.name, 'from_date', roster_doc.from_date)
			if relieving_date:
				if relieving_date <= roster_doc.to_date:
					frappe.db.set_value('Roster Details', emp.name, 'to_date', emp_doc.relieving_date)
				else:
					frappe.db.set_value('Roster Details', emp.name, 'to_date', roster_doc.to_date)
			else:
				frappe.db.set_value('Roster Details', emp.name, 'to_date', roster_doc.to_date)
			print ("S.No. " + str(count) + "." + str(count_emp) + " Roster = " + rost[0] + \
				" Employee = " + emp_doc.employee_name + " Update with Child Tables")
