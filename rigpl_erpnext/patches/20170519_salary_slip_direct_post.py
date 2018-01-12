# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe, erpnext
from frappe.utils import flt
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_month_details

def execute():
	'''
	This patch is to cancel the JV associated with Salary Slip Payment and
	then repost the Salary Slip in GL Entry
	'''
	ssp_list = frappe.db.sql("""SELECT name FROM `tabSalary Slip Payment` 
		WHERE docstatus = 1 ORDER BY name""", as_list=1)
		
	for ssp in ssp_list:
		#Find the JV which is linked to the SSP and Cancel it.
		jv_list = frappe.db.sql("""SELECT jv.name FROM `tabJournal Entry` jv,
			`tabJournal Entry Account` jva
			WHERE 
			jv.docstatus = 1 AND
			jva.parent = jv.name AND
			jva.reference_type = 'Salary Slip Payment' AND 
			jva.reference_name = '%s'
			GROUP BY jv.name""" %(ssp[0]), as_list=1)
			
		for jv in jv_list:
			jv_doc = frappe.get_doc("Journal Entry", jv[0])
			jv_doc.cancel()
			print "Cancelled JV# " + jv[0]
	#Check the Salary Slips in the SSP if they are posted or NOT, if NOT posted then POST
		ssp_doc = frappe.get_doc("Salary Slip Payment", ssp[0])
		count = 0
		for ss in ssp_doc.salary_slip_payment_details:
			count += 1
			print "Processing Row# " + str(count)
			ss_doc = frappe.get_doc("Salary Slip", ss.salary_slip)
			ss_posted = frappe.db.sql("""SELECT name FROM `tabGL Entry` WHERE docstatus =1 AND
				voucher_type = 'Salary Slip' AND voucher_no = '%s'
				"""%(ss.salary_slip), as_list=1)
			if not ss_posted:
				from rigpl_erpnext.rigpl_erpnext.validations.salary_slip import post_gl_entry
				post_gl_entry(ss_doc)
				print "Row# " + str(count) + " Salary Slip # :" + ss.salary_slip + " Posted"
		ssp_doc = frappe.get_doc("Salary Slip Payment", ssp[0])
		ssp_doc.cancel()
		print "Salary Slip Payment # " + ssp[0] + " Cancelled"
