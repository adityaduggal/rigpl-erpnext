# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.utils import getdate
import frappe
from frappe.model.document import Document
import math

class EmployeeLoan(Document):
	def validate(self):
		self.total_loan = 0
		for i in self.employee_loan_detail:
			#Populate Employee Name from ID
			i.employee_name = frappe.get_doc("Employee", i.employee).employee_name

			#Change values as per the loan amount
			if i.loan_amount != i.emi * i.repayment_period:
				if i.emi%100 !=0:
					i.emi = int(math.ceil(i.emi/100))*100
				i.repayment_period = i.loan_amount/i.emi
					
			
			#Check negative values:
			if (i.loan_amount % 100 != 0 or i.emi % 100 != 0):
				frappe.throw("Loan Amount and EMI should be multiples of 100")
			if (i.repayment_period % 1 != 0):
				frappe.throw("Repayment period should be an Integer")
			if (i.loan_amount < 0 or i.emi < 0 or i.repayment_period < 0):
				frappe.throw("Loan Amount, EMI and Repayment Period should be greater than ZERO")
				
			#Check Duplicate Employee
			all_employee = []
			for j in self.employee_loan_detail:
				all_employee.append (j.employee)
			if all_employee.count(i.employee)>1:
				frappe.throw(("{0} is entered multiple times").format(i.employee_name))
			
			#Don't allow inactive employees on that date
			emp = frappe.get_doc("Employee", i.employee)
			pd = getdate(self.posting_date)
			rd = getdate(emp.relieving_date)
			if emp.status <> "Active" and rd < pd:
				frappe.throw(("{0} left on {1} hence cannot give advance on {2}").\
					format(i.employee_name, rd, pd))
			self.total_loan += i.loan_amount