# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import money_in_words
from erpnext.setup.utils import get_company_currency
from erpnext.hr.doctype.process_payroll.process_payroll import get_month_details
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee

def on_update(doc,method):
	gross_pay = 0
	net_pay = 0
	total_deductions = 0
	
	m = get_month_details(doc.fiscal_year, doc.month)
	total_days_in_month = m["month_days"]
	holiday_list = get_holiday_list_for_employee(doc.employee)
	holidays = frappe.db.sql("""SELECT count(name) FROM `tabHoliday` WHERE parent = '%s' AND 
		holiday_date >= '%s' AND holiday_date <= '%s'""" %(holiday_list, \
			m.month_start_date, m.month_end_date), as_list=1)

	att = frappe.db.sql("""SELECT sum(overtime), count(name) FROM `tabAttendance` 
		WHERE employee = '%s' AND att_date >= '%s' AND att_date <= '%s' 
		AND status = 'Present' AND docstatus=1""" \
		%(doc.employee,m.month_start_date, m.month_end_date),as_list=1)

	doc.total_overtime = att[0][0]
	total_presents = att[0][1]
	doc.unauthorized_leaves = total_days_in_month - total_presents - \
		doc.leave_without_pay - holidays[0][0]
	doc.overtime_deducted = round(8*doc.unauthorized_leaves,1)
	
	for d in doc.earnings:
		earn = frappe.get_doc("Earning Type", d.e_type)
		if earn.based_on_overtime:
			for d2 in doc.earnings:
				if earn.overtime_rate == d2.e_type:
					d.e_amount = d2.e_amount * (doc.total_overtime)
					d.e_modified_amount = d2.e_amount * (doc.total_overtime - doc.overtime_deducted)
		else:
			if earn.only_for_deductions <> 1:
				d.e_modified_amount = round(d.e_amount * (total_days_in_month - \
					doc.unauthorized_leaves - doc.leave_without_pay)/total_days_in_month,0)
		if earn.only_for_deductions <> 1:
			gross_pay += d.e_modified_amount
		
	for d in doc.deductions:
		deduct = frappe.get_doc("Deduction Type", d.d_type)
		if deduct.based_on_earning:
			for e in doc.earnings:
				if deduct.earning == e.e_type:
					d.d_modified_amount = round((e.e_amount * deduct.percentage * \
						(total_days_in_month - doc.unauthorized_leaves - \
							doc.leave_without_pay)/total_days_in_month)/100,0)
		#total_deductions +=d.d_modified_amount
	
	doc.gross_pay = gross_pay
	doc.net_pay = doc.gross_pay - doc.total_deduction
	doc.rounded_total = myround(doc.net_pay, 10)
	company_currency = get_company_currency(doc.company)
	doc.total_in_words = money_in_words(doc.rounded_total, company_currency)
	
def myround(x, base=5):
    return int(base * round(float(x)/base))
	