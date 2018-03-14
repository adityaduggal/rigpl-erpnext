# -*- coding: utf-8 -*-
import frappe
from frappe.utils import flt
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_month_details

def execute():
	'''
	This patch is to update the status of Expense Claim
	docstatus = 0 => Status = Draft
	docstatus = 2 => Status = Cancelled
	docstatus = 1 and sanctioned < paid => Status = Unpaid
	docstatus = 1 and sanctioned = paid => Status = Paid
	'''
	ec_list = frappe.db.sql("""SELECT name FROM `tabExpense Claim` """, as_list=1)
	for ec in ec_list:
		ec_doc = frappe.get_doc("Expense Claim", ec[0])
		if ec_doc.docstatus == 2:
			if ec_doc.status != "Cancelled":
				frappe.db.set_value("Expense Claim", ec[0], "status", "Cancelled")
				print ("Status of " + ec[0] + " set to Cancelled")
		elif ec_doc.docstatus == 0:
			if ec_doc.status != "Draft":
				frappe.db.set_value("Expense Claim", ec[0], "status", "Draft")
				print ("Status of " + ec[0] + " set to Draft")
		elif ec_doc.docstatus == 1:
			if ec_doc.total_sanctioned_amount == ec_doc.total_amount_reimbursed:
				if ec_doc.status != "Paid":
					frappe.db.set_value("Expense Claim", ec[0], "status", "Paid")
					print ("Status of " + ec[0] + " set to Paid")
			elif ec_doc.total_sanctioned_amount < ec_doc.total_amount_reimbursed:
				if ec_doc.total_amount_reimbursed > 0:
					print ("Error for " + ec[0])
				else:
					if ec_doc.status != "Unpaid":
						frappe.db.set_value("Expense Claim", ec[0], "status", "Unpaid")
						print ("Status of " + ec[0] + " set to Unpaid")
				
			
