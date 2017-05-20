# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.utils import getdate
import frappe
from frappe.model.document import Document
from frappe.utils import flt
from erpnext.accounts.general_ledger import make_gl_entries, delete_gl_entries
from erpnext.accounts.utils import get_fiscal_years, validate_fiscal_year, get_account_currency
import math

class EmployeeAdvance(Document):
	def validate(self):
		self.total_loan = 0
		for i in self.employee_loan_detail:
			#Populate Employee Name from ID
			i.employee_name = frappe.get_doc("Employee", i.employee).employee_name

			#Change values as per the loan amount
			if i.loan_amount != i.emi * i.repayment_period:
				if i.emi%10 !=0:
					i.emi = int(math.ceil(i.emi/10))*10
				i.repayment_period = i.loan_amount/i.emi
					
			
			#Check negative values:
			if (i.loan_amount % 10 != 0 or i.emi % 10 != 0):
				frappe.throw("Loan Amount and EMI should be multiples of 10")
			#if (i.repayment_period % 1 != 0):
			#	frappe.throw("Repayment period should be an Integer")
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
	
	def on_update(self):
		pass
	
	def on_submit(self):
		gl_map = []
		fiscal_years = get_fiscal_years(self.posting_date, company='RIGPL')
		if len(fiscal_years) > 1:
			frappe.throw(_("Multiple fiscal years exist for the date {0}. \
				Please set company in Fiscal Year").format(formatdate(self.posting_date)))
		else:
			fiscal_year = fiscal_years[0][0]
		
		for emp in self.employee_loan_detail:
			if emp.loan_amount:
				gl_dict = frappe._dict({
					'company': 'RIGPL',
					'posting_date' : self.posting_date,
					'fiscal_year': fiscal_year,
					'voucher_type': 'Employee Advance',
					'voucher_no': self.name,
					'account': self.debit_account,
					'debit': flt(emp.loan_amount),
					'debit_in_account_currency': flt(emp.loan_amount),
					'party_type': 'Employee',
					'party': emp.employee,
					'against': self.credit_account
				})
				gl_map.append(gl_dict)
		if gl_map:
			gl_dict = frappe._dict({
				'company': 'RIGPL',
				'posting_date' : self.posting_date,
				'fiscal_year': fiscal_year,
				'voucher_type': 'Employee Advance',
				'voucher_no': self.name,
				'account': self.credit_account,
				'debit': 0,
				'credit': flt(self.total_loan),
				'credit_in_account_currency' : flt(self.total_loan),
				'debit_in_account_currency': 0,
				'against': self.debit_account
			})
			gl_map.append(gl_dict)
			make_gl_entries(gl_map, cancel=0, adv_adj=0)

	def on_cancel(self):
		delete_gl_entries(None, 'Employee Advance', self.name)
