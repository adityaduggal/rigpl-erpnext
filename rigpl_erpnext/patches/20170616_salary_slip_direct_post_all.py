# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe, erpnext
from frappe.utils import flt
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_month_details

def execute():
	'''
	This patch posts all unposted Salary Slips to GL
	'''
	ss_list = frappe.db.sql("""SELECT name FROM `tabSalary Slip` 
		WHERE docstatus = 1 ORDER BY name""", as_list=1)
	for ss in ss_list:
		ss_doc = frappe.get_doc("Salary Slip", ss[0])
		ss_posted = frappe.db.sql("""SELECT name FROM `tabGL Entry` WHERE docstatus =1 AND
			voucher_type = 'Salary Slip' AND voucher_no = '%s'
			"""%(ss_doc.name), as_list=1)
			
		if not ss_posted:
			from rigpl_erpnext.rigpl_erpnext.validations.salary_slip import post_gl_entry
			post_gl_entry(ss_doc)
			print ("Salary Slip # :" + ss[0] + " Posted in GL")
