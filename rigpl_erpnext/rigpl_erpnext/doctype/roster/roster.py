# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days, add_years, cstr
from frappe import msgprint, _

class Roster(Document):
	def validate(self):
		#Checks to be done:
		#From date should be greater than to date.
		#No 2 rosters for same shift within a time period (THIS IS WRONG)
		#No repeat of employee in 1 rosters (Done)
		#No repeat of employee in 2 concurrent rosters.(Done)
		
		self.validate_dates()
		self.validate_employee()
		#self.validate_roster_date_range() #Check date range for rosters of same shift
		self.check_employee_across_shifts()
	
	def validate_dates(self):
		if self.to_date:
			if getdate(self.to_date) < getdate(self.from_date):
				frappe.throw(_("From Date should not be greater than To Date"))
		for d in self.get('employees'):
			if getdate(d.to_date) < getdate(d.from_date):
				frappe.throw(_("From Date should not be greater than To Date in Row # {0}").format(d.idx))
			if getdate(d.to_date) <> getdate(self.to_date):
				d.to_date = self.to_date
			if getdate(d.from_date) <> getdate(self.from_date):
				d.from_date = self.from_date
	
	def validate_employee(self):
		emp = []
		for d in self.get('employees'):
			emp.append(d.employee)
			emp_db = frappe.get_doc("Employee", d.employee)
			d.employee_name = emp_db.employee_name
			d.employee_number = emp_db.employee_number
			if emp_db.status != "Active":
				if getdate(emp_db.relieving_date) < getdate(d.from_date):
					frappe.throw(("Employee {0} selected is not active as \
					he/she was Relieved on {1} in Row # {2}").format(d.employee_name, 
					getdate(emp_db.relieving_date), d.idx))
				elif getdate(emp_db.relieving_date) < getdate(d.to_date):
					d.to_date = getdate(emp_db.relieving_date)		
		
		if len(emp)!=len(set(emp)):
			frappe.throw("Employee List has repeated employees")
		
	def validate_roster_date_range(self):
		roster = frappe.db.sql("""SELECT name from `tabRoster` 
				WHERE docstatus = 0 """)
		for i in range(len(roster)):
			r_chk = frappe.get_doc("Roster", roster[i][0])
			if r_chk.to_date is None:
				r_chk.to_date = getdate('2099-12-31 00:00:00')
			
			if self.to_date is None:
				self.to_date = getdate('2099-12-31 00:00:00')
				
			if r_chk.shift == self.shift and r_chk.name != self.name:
				if getdate(self.from_date) >= getdate(r_chk.from_date) and getdate(self.from_date) <= getdate(r_chk.to_date):
					frappe.throw(("Date Range Selected overlaps with {0} check the From Date").format(r_chk.name))
					
				if getdate(self.to_date) >= getdate(r_chk.from_date) and getdate(self.to_date) <= getdate(r_chk.to_date):
					frappe.throw(("Date Range Selected overlaps with {0} check the To Date").format(r_chk.name))
	
	def check_employee_across_shifts(self):
		oth_roster = frappe.db.sql("""SELECT ro.name, ro.shift, rod.employee, ro.from_date, ro.to_date
			FROM `tabRoster` ro, `tabRoster Details` rod 
			WHERE rod.parent = ro.name AND ro.docstatus = 0
			ORDER BY ro.name, rod.employee""")
		for i in oth_roster:
			if self.name != i[0] and self.shift != i[1]:
				if ((getdate(self.from_date) >= i[3] and getdate(self.from_date) <= i[4]) 
					or (getdate(self.to_date) >= i[3] and getdate(self.to_date) <= i[4])):
					
					#The above condition proves that there is an overlapping roster for different shift
					#Now we need to check if the overlapping rosters don't have same employees since
					#1 employee cannot be alloted to 2 shifts for same period
					#emp = []
					for d in self.get('employees'):
						if d.employee == i[2]:
							frappe.throw(("Employee # {0} is already allotted to Roster# {1} \
							for Shift# {2} which overlaps with current roster")
							.format(i[2], i[0], i[1]))
					
		
			
		
