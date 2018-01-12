# -*- coding: utf-8 -*-
import frappe
from frappe.utils import flt
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_month_details

def execute():
	'''
	This patch is to change the Employee Loan Doctype to Employee Advance
	1. Parent Type of Employee Loan Detail to  be Changed from Employee Loan to Employee Advance
	2. Reference Type of Journal Voucher Account to be Changed from Employee Loan to Employee Advance
	3. Reference Type in Salary Slip to be Changed check this is not linked directly
	'''
	frappe.db.sql("""UPDATE `tabEmployee Loan Detail` SET parenttype = 'Employee Advance'""")
	frappe.db.sql("""UPDATE `tabJournal Entry Account` SET reference_type = 'Employee Advance'
		WHERE reference_type = 'Employee Loan' """)
