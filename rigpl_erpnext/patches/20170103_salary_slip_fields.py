# -*- coding: utf-8 -*-
import frappe
from frappe.utils import flt
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_month_details

def execute():
	'''
	Update the following fields in Salary Slip:
	1. Status field, if docstatus = 2, Cancelled etc, Paid if its linked to SSP
	2. Frequency = Monthly
	3. Start Date and End Date as per FY and Month
	4. Posting Date as end of the month
	'''
	salary_slips = frappe.db.sql("""SELECT ss.name FROM `tabSalary Slip` ss""", as_list=1)
	
	for ss in salary_slips:
		ss_doc = frappe.get_doc("Salary Slip", ss[0])
		if ss_doc.docstatus == 2:
			if ss_doc.status != "Cancelled":
				frappe.db.set_value("Salary Slip", ss[0], "status", "Cancelled")
				print ("Status of " + ss[0] + " set to Cancelled")
		elif ss_doc.docstatus == 0:
			if ss_doc.status != "Draft":
				frappe.db.set_value("Salary Slip", ss[0], "status", "Draft")
				print ("Status of " + ss[0] + " set to Draft")
		if ss_doc.payroll_frequency != "Monthly":
			frappe.db.set_value("Salary Slip", ss[0], "payroll_frequency", "Monthly")
			print ("Frequency of " + ss[0] + " set to Monthly")
		if ss_doc.fiscal_year is not None:
			m = get_month_details(ss_doc.fiscal_year, ss_doc.month)
			start_date = m['month_start_date']
			end_date = m['month_end_date']
			frappe.db.set_value("Salary Slip", ss[0], "start_date", start_date)
			frappe.db.set_value("Salary Slip", ss[0], "end_date", end_date)
			frappe.db.set_value("Salary Slip", ss[0], "posting_date", end_date)
			print ("Start, End and Posting Date for " + ss[0] + " set.")
