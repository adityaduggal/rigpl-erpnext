# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def execute():
	#This code needs to be run manually since some custom fields are first applied to
	#-Attendance, Salary Structure Assignment and then only they are imported back
	#Code to move the custom fields from Salary Structure Employee to the Custom Fields of 

	ssa_list = frappe.db.sql("""SELECT name, employee, employee_name, from_date, salary_structure
		FROM `tabSalary Structure Assignment`""", as_dict=1)

	for ssa in ssa_list:
		print("Checking for SSA " + ssa.name + " for Employee " + \
			ssa.employee + " and Name " + ssa.employee_name)

		ssemp = frappe.db.sql("""SELECT to_date, minimum_applicable, basic_percent
			FROM `tabSalary Structure Employee` WHERE parent = '%s' AND employee = '%s'
			AND from_date = '%s'"""%(ssa.salary_structure, ssa.employee, ssa.from_date), as_dict=1)

		if ssemp:
			if len(ssemp) == 1:
				frappe.db.set_value("Salary Structure Assignment", \
					ssa.name, "to_date", ssemp[0].to_date)
				frappe.db.set_value("Salary Structure Assignment", \
					ssa.name, "minimum_applicable", ssemp[0].minimum_applicable)
				frappe.db.set_value("Salary Structure Assignment", \
					ssa.name, "basic_percent", ssemp[0].basic_percent)
				frappe.db.commit()
				print("Updated SSA " + ssa.name)
			else:
				print("Multiple Values found for Emp: " + ssa.employee)
		else:
			print("No Values found for Emp: " + ssa.employee)


	#Old shift has to be created manually in the Shift Type due to custom fields in Shift Details
	#Code to change the old shift to the new shift in ATTENDANCE
	att_with_shift = frappe.db.sql("""SELECT name, shift, attendance_date 
		FROM `tabAttendance` 
		WHERE shift IS NOT NULL AND shift NOT IN (SELECT name 
			FROM `tabShift Type`)
		ORDER BY attendance_date""",as_list=1)

	for att in att_with_shift:
		chk_new_shift = frappe.db.sql("""SELECT name FROM `tabShift Type`
			WHERE name = '%s'"""%(att[1]), as_list=1)
		if chk_new_shift:
			print("New Shift " + att[1] + \
				" Already Linked with Attendance " + att[0])
		else:
			new_shift = frappe.db.sql("""SELECT name FROM `tabShift Type` 
				WHERE old_shift_name = '%s'"""%(att[1]), as_list=1)
			if new_shift:
				frappe.db.set_value("Attendance", att[0], "shift", new_shift[0][0])
				print("Updated Attendance " + att[0] + " with New Shift " + \
					new_shift[0][0])
			else:
				print("New Shift " + att[1] +" Not found for Attendance " + att[0])
	
	#Code to Change the Roster to Shift Request and also this would create shift assignment
	roster_list = frappe.db.sql("""SELECT name, shift FROM `tabRoster`""", as_list=1)
	for ros in roster_list:
		ros_doc = frappe.get_doc("Roster", ros[0])
		to_remove = []
		for row in ros_doc.employees:
			if row.from_date > row.to_date:
				to_remove.append(row)
				print("Check " + ros_doc.name + " Row # " + str(row.idx))
		if to_remove:
			[ros_doc.remove(d) for d in to_remove]
			ros_doc.save()
			frappe.db.commit()
			print("Saved Roster " + ros_doc.name)

	for ros in roster_list:
		print("Working on Roster " + ros[0])
		ros_doc = frappe.get_doc("Roster", ros[0])
		new_shift = frappe.get_value("Shift Type", {"old_shift_name": ros[1]}, "name")
		for row in ros_doc.employees:
			chk_shft_req = frappe.db.sql("""SELECT name FROM `tabShift Request` 
				WHERE shift_type = '%s' AND employee = '%s' AND from_date = '%s' 
				AND to_date = '%s'"""%(new_shift, row.employee, \
					row.from_date, row.to_date), as_list=1)
			if chk_shft_req:
				print("For Roster " + ros[0] + " and employee " + \
					row.employee_name + " shift request exists " + chk_shft_req[0][0])
			else:
				shft_req = frappe.new_doc("Shift Request")
				shft_req.shift_type = new_shift
				shft_req.employee = row.employee
				shft_req.from_date = row.from_date
				shft_req.to_date = row.to_date
				shft_req.flags.ignore_permissions = True
				shft_req.insert()
				frappe.db.commit()
				print("Created Shift Request " + shft_req.name + \
					" for Employee " + row.employee_name + " from date " \
					+ str(row.from_date) + " to date " + str(row.to_date))
				shft_req_to_submit = frappe.get_doc("Shift Request", shft_req.name)
				shft_req_to_submit.submit()
				frappe.db.commit()
				print("Submitted Shift Request " + shft_req_to_submit.name + \
					" for Employee " + row.employee_name + " from date " + \
					str(row.from_date) + " to date " + str(row.to_date))
			
