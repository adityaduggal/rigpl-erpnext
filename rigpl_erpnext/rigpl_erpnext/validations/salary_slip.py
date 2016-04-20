# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import money_in_words, flt
from erpnext.setup.utils import get_company_currency
from erpnext.hr.doctype.process_payroll.process_payroll import get_month_details
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee

def on_submit(doc,method):
	if doc.net_pay < 0:
		frappe.throw("Negative Net Pay Not Allowed")
	#Update the expense claim amount cleared so that no new JV can be made
	for i in doc.earnings:
		if i.expense_claim:
			ec = frappe.get_doc("Expense Claim", i.expense_claim)
			frappe.db.set_value("Expense Claim", i.expense_claim, "total_amount_reimbursed", \
				i.e_modified_amount)

			

def on_cancel(doc,method):
	#Update the expense claim amount cleared so that no new JV can be made
	for i in doc.earnings:
		if i.expense_claim:
			ec = frappe.get_doc("Expense Claim", i.expense_claim)
			frappe.db.set_value("Expense Claim", i.expense_claim, "total_amount_reimbursed", 0)
	
def validate(doc,method):
	gross_pay = 0
	net_pay = 0
	tot_ded = 0
	get_loan_deduction(doc,method)
	get_expense_claim(doc,method)
	
	m = get_month_details(doc.fiscal_year, doc.month)
	tdim = m["month_days"] #total days in a month
	lwp = flt(doc.leave_without_pay)
	
	holiday_list = get_holiday_list_for_employee(doc.employee)
	holidays = frappe.db.sql("""SELECT count(name) FROM `tabHoliday` WHERE parent = '%s' AND 
		holiday_date >= '%s' AND holiday_date <= '%s'""" %(holiday_list, \
			m.month_start_date, m.month_end_date), as_list=1)
	
	holidays = holidays[0][0] #no of holidays in a month from the holiday list
	wd = tdim - holidays #total working days
	
	att = frappe.db.sql("""SELECT sum(overtime), count(name) FROM `tabAttendance` 
		WHERE employee = '%s' AND att_date >= '%s' AND att_date <= '%s' 
		AND status = 'Present' AND docstatus=1""" \
		%(doc.employee,m.month_start_date, m.month_end_date),as_list=1)

	t_ot = flt(att[0][0])
	doc.total_overtime = t_ot
	tpres = att[0][1]
	ual = tdim - tpres - lwp - holidays
	if ual < 0:
		frappe.throw("Unauthorized Leave cannot be Negative")
	paydays = tdim - lwp - ual + round(((wd/tdim)*holidays),0)
	
	doc.unauthorized_leaves = ual 
	
	ot_ded = round(8*ual,1)
	doc.overtime_deducted = ot_ded
	
	for d in doc.earnings:
		earn = frappe.get_doc("Earning Type", d.e_type)
		if earn.based_on_overtime:
			for d2 in doc.earnings:
				if earn.overtime_rate == d2.e_type:
					d.e_amount = flt(d2.e_amount) * t_ot
					d.e_modified_amount = flt(d2.e_amount) * (t_ot - ot_ded)
		else:
			if d.e_depends_on_lwp == 1:
				d.e_modified_amount = round(flt(d.e_amount) * paydays/tdim,0)
		if earn.only_for_deductions <> 1:
			gross_pay += flt(d.e_modified_amount)
	if gross_pay < 0:
		doc.arrear_amount = -1 * gross_pay
	gross_pay += flt(doc.arrear_amount) + flt(doc.leave_encashment_amount)
		
	for d in doc.deductions:
		deduct = frappe.get_doc("Deduction Type", d.d_type)
		if deduct.based_on_earning:
			for e in doc.earnings:
				if deduct.earning == e.e_type:
					d.d_modified_amount = round((flt(e.e_amount) * deduct.percentage * \
						paydays/tdim)/100,0)
		tot_ded +=d.d_modified_amount
	
	doc.gross_pay = gross_pay
	doc.total_deduction = tot_ded
	doc.payment_days = paydays
	doc.net_pay = doc.gross_pay - doc.total_deduction
	doc.rounded_total = myround(doc.net_pay, 10)
		
	company_currency = get_company_currency(doc.company)
	doc.total_in_words = money_in_words(doc.rounded_total, company_currency)

def get_loan_deduction(doc,method):
	m = get_month_details(doc.fiscal_year, doc.month)
	#get total loan due for employee
	query = """SELECT el.name, eld.name, eld.emi, el.deduction_type, eld.loan_amount
		FROM 
			`tabEmployee Loan` el, `tabEmployee Loan Detail` eld
		WHERE
			eld.parent = el.name AND
			el.docstatus = 1 AND el.posting_date <= '%s' AND
			eld.employee = '%s'""" %(m.month_end_date, doc.employee)
	
	loan_list = frappe.db.sql(query, as_list=1)
	
	for i in loan_list:
		existing_loan = []
		for d in doc.deductions:
			existing_loan.append(d.employee_loan)

		if i[0] not in existing_loan:
			#Check if the loan has already been deducted
			query = """SELECT SUM(ssd.d_modified_amount) 
				FROM `tabSalary Slip Deduction` ssd, `tabSalary Slip` ss
				WHERE ss.docstatus = 1 AND
					ssd.parent = ss.name AND
					ssd.employee_loan = '%s'""" %i[0]
			deducted_amount = frappe.db.sql(query, as_list=1)
			
			if i[4] > deducted_amount[0][0]:
				#Add deduction for each loan separately
				doc.append("deductions", {
					"idx": len(doc.deductions)+1, "d_depends_on_lwp": 0, "d_modified_amount": i[2], \
					"employee_loan": i[0], "d_type": i[3], "d_amount": i[2]
				})

def get_expense_claim(doc,method):
	m = get_month_details(doc.fiscal_year, doc.month)
	#Get total Expense Claims Due for an Employee
	query = """SELECT ec.name, ec.employee, ec.total_sanctioned_amount, ec.total_amount_reimbursed,
		ec.earning_type
		FROM `tabExpense Claim` ec
		WHERE ec.docstatus = 1 AND ec.approval_status = 'Approved' AND
			ec.total_amount_reimbursed < ec.total_sanctioned_amount AND
			ec.posting_date <= '%s' AND ec.employee = '%s'""" %(m.month_end_date, doc.employee)
	
	
	ec_list = frappe.db.sql(query, as_list=1)
		
	for i in ec_list:
		existing_ec = []
		for e in doc.earnings:
			existing_ec.append(e.expense_claim)
		
		if i[0] not in existing_ec:
			#Add earning claim for each EC separately:
			doc.append("earnings", {
				"idx": len(doc.earnings)+1, "e_depends_on_lwp": 0, "e_modified_amount": (i[2]-i[3]), \
				"expense_claim": i[0], "e_type": i[4], "e_amount": (i[2]- i[3])
			})

	
def myround(x, base=5):
    return int(base * round(float(x)/base))

	