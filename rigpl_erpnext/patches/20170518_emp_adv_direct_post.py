# -*- coding: utf-8 -*-
import frappe
from frappe.utils import flt
from erpnext.hr.doctype.process_payroll.process_payroll import get_month_details

def execute():
	'''
	This patch is to cancel the JV associated with Employee Loan and Employee Advance and
	then repost the Employee Advance in GL Entry
	'''
	gl_adv_list = frappe.db.sql("""SELECT name, voucher_no, against_voucher FROM `tabGL Entry` 
		WHERE docstatus = 1 AND (against_voucher_type = 'Employee Loan' OR 
		against_voucher_type = 'Employee Advance') AND voucher_type = 'Journal Entry'
		GROUP BY voucher_no""", as_list=1)
		
	for jv in gl_adv_list:
		jv_doc = frappe.get_doc("Journal Entry", jv[1])
		jv_doc.cancel()
		print "Journal Entry #" + jv[1] + " Cancelled."
		
		#Check and post the employee advance directly into the GL
		from erpnext.accounts.general_ledger import make_gl_entries
		from erpnext.accounts.utils import get_fiscal_years, validate_fiscal_year, get_account_currency
		
		#Check if emp_adv_doc already posted into the GL or NOT
		gl_entry_adv = frappe.db.sql("""SELECT name FROM `tabGL Entry` WHERE
			docstatus = 1 AND voucher_type = 'Employee Advance' 
			AND voucher_no = '%s'""" % (jv[2]), as_list=1)
			
		if gl_entry_adv:
			pass
			#donot post gl if already exists
		else:		
			emp_adv_doc = frappe.get_doc("Employee Advance", jv[2])
			gl_map = []
		
			fiscal_years = get_fiscal_years(emp_adv_doc.posting_date, company='RIGPL')
			if len(fiscal_years) > 1:
				frappe.throw(_("Multiple fiscal years exist for the date {0}. \
					Please set company in Fiscal Year").format(formatdate(self.posting_date)))
			else:
				fiscal_year = fiscal_years[0][0]
		
			for emp in emp_adv_doc.employee_loan_detail:
				if emp.loan_amount:
					gl_dict = frappe._dict({
						'company': 'RIGPL',
						'posting_date' : emp_adv_doc.posting_date,
						'fiscal_year': fiscal_year,
						'voucher_type': 'Employee Advance',
						'voucher_no': emp_adv_doc.name,
						'account': emp_adv_doc.debit_account,
						'debit': flt(emp.loan_amount),
						'debit_in_account_currency': flt(emp.loan_amount),
						'party_type': 'Employee',
						'party': emp.employee,
						'against': emp_adv_doc.credit_account
					})
					gl_map.append(gl_dict)
			if gl_map:
				gl_dict = frappe._dict({
					'company': 'RIGPL',
					'posting_date' : emp_adv_doc.posting_date,
					'fiscal_year': fiscal_year,
					'voucher_type': 'Employee Advance',
					'voucher_no': emp_adv_doc.name,
					'account': emp_adv_doc.credit_account,
					'debit': 0,
					'credit': flt(emp_adv_doc.total_loan),
					'credit_in_account_currency' : flt(emp_adv_doc.total_loan),
					'debit_in_account_currency': 0,
					'against': emp_adv_doc.debit_account
				})
				gl_map.append(gl_dict)
				make_gl_entries(gl_map, cancel=0, adv_adj=0)
				print "Employee Advance #" + emp_adv_doc.name + " Posted to GL Entry"
