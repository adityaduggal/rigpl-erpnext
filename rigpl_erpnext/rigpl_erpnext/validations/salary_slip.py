# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import math
import datetime
from frappe import msgprint
from frappe.model.mapper import get_mapped_doc
from frappe.utils import money_in_words, flt
from erpnext.setup.utils import get_company_currency
from erpnext.hr.doctype.process_payroll.process_payroll import get_month_details
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee
from erpnext.hr.doctype.salary_slip.salary_slip import SalarySlip

def on_submit(doc,method):
	if doc.net_pay < 0:
		frappe.throw("Negative Net Pay Not Allowed")
	#Update the expense claim amount cleared so that no new JV can be made
	for i in doc.earnings:
		if i.expense_claim:
			ec = frappe.get_doc("Expense Claim", i.expense_claim)
			frappe.db.set_value("Expense Claim", i.expense_claim, "total_amount_reimbursed", \
				i.amount)
			

def on_cancel(doc,method):
	#Update the expense claim amount cleared so that no new JV can be made
	for i in doc.earnings:
		if i.expense_claim:
			ec = frappe.get_doc("Expense Claim", i.expense_claim)
			frappe.db.set_value("Expense Claim", i.expense_claim, "total_amount_reimbursed", 0)
	
def validate(doc,method):
	get_edc(doc)
	month, msd, med = get_month_dates(doc)
	get_loan_deduction(doc, msd, med)
	get_expense_claim(doc)
	calculate_net_salary(doc, month, msd, med)
	
def calculate_net_salary(doc, month, msd, med):
	gross_pay = 0
	net_pay = 0
	tot_ded = 0
	tot_cont = 0
	
	emp = frappe.get_doc("Employee", doc.employee)
	tdim, twd = get_total_days(doc, emp, msd, med, month)
	holidays = get_holidays(doc, msd, med, emp)
	lwp, plw = get_leaves(doc, msd, med, emp)
	doc.leave_without_pay = lwp
	doc.posting_date = month.month_end_date
	wd = twd - holidays #total working days
	doc.total_days_in_month = tdim
	att = frappe.db.sql("""SELECT sum(overtime), count(name) FROM `tabAttendance` 
		WHERE employee = '%s' AND att_date >= '%s' AND att_date <= '%s' 
		AND status = 'Present' AND docstatus=1""" \
		%(doc.employee, msd, med),as_list=1)

	half_day = frappe.db.sql("""SELECT count(name) FROM `tabAttendance` 
		WHERE employee = '%s' AND att_date >= '%s' AND att_date <= '%s' 
		AND status = 'Half Day' AND docstatus=1""" \
		%(doc.employee, msd, med),as_list=1)
	
	t_hd = flt(half_day[0][0])
	t_ot = flt(att[0][0])
	doc.total_overtime = t_ot
	tpres = flt(att[0][1])

	ual = twd - tpres - lwp - holidays - plw - (t_hd/2)
	
	if ual < 0:
		frappe.throw(("Unauthorized Leave cannot be Negative for Employee {0}").\
			format(doc.employee_name))
	
	paydays = tpres + (t_hd/2) + plw + math.ceil((tpres+(t_hd/2))/wd * holidays)
	pd_ded = flt(doc.payment_days_for_deductions)
	doc.payment_days = paydays
	
	if doc.change_deductions == 0:
		doc.payment_days_for_deductions = doc.payment_days
	
	doc.unauthorized_leaves = ual 
	
	ot_ded = round(8*ual,1)
	if ot_ded > t_ot:
		ot_ded = (int(t_ot/8))*8
	doc.overtime_deducted = ot_ded
	d_ual = int(ot_ded/8)
	
	#Calculate Earnings
	chk_ot = 0 #Check if there is an Overtime Rate
	for d in doc.earnings:
		if d.salary_component == "Overtime Rate":
			chk_ot = 1
			
	for d in doc.earnings:
		earn = frappe.get_doc("Salary Component", d.salary_component)
		if earn.depends_on_lwp == 1:
			d.depends_on_lwp = 1
		else:
			d.depends_on_lwp = 0
		
		if earn.based_on_earning:
			for d2 in doc.earnings:
				#Calculate Overtime Value
				if earn.earning == d2.salary_component:
					d.default_amount = flt(d2.amount) * t_ot
					d.amount = flt(d2.amount) * (t_ot - ot_ded)
		else:
			if d.depends_on_lwp == 1 and earn.books == 0:
				if chk_ot == 1:
					d.amount = round(flt(d.default_amount) * (paydays+d_ual)/tdim,0)
				else:
					d.amount = round(flt(d.default_amount) * (paydays)/tdim,0)
			elif d.depends_on_lwp == 1 and earn.books == 1:
				d.amount = round(flt(d.default_amount) * flt(doc.payment_days_for_deductions)/ tdim,0)
			else:
				d.amount = d.default_amount
		
		if earn.only_for_deductions <> 1:
			gross_pay += flt(d.amount)

	if gross_pay < 0:
		doc.arrear_amount = -1 * gross_pay
	gross_pay += flt(doc.arrear_amount) + flt(doc.leave_encashment_amount)
	
	#Calculate Deductions
	for d in doc.deductions:
		#Check if deduction is in any earning's formula
		chk = 0
		for e in doc.earnings:
			earn = frappe.get_doc("Salary Component", e.salary_component)
			for form in earn.deduction_contribution_formula:
				if d.salary_component == form.salary_component:
					chk = 1
					d.amount = 0
		if chk == 1:
			for e in doc.earnings:
				earn = frappe.get_doc("Salary Component", e.salary_component)
				for form in earn.deduction_contribution_formula:
					if d.salary_component == form.salary_component:
						d.default_amount = flt(e.default_amount) * flt(form.percentage)/100
						d.amount += flt(e.amount) * flt(form.percentage)/100
			d.amount = round(d.amount,0)
			d.default_amount = round(d.default_amount,0)
		elif d.salary_component <> 'Loan Deduction':
			str = frappe.get_doc("Salary Structure", doc.salary_structure)
			for x in str.deductions:
				if x.salary_component == d.salary_component:
					d.default_amount = x.amount
					d.amount = d.default_amount

		tot_ded +=d.amount
	
	#Calculate Contributions
	for c in doc.contributions:
		#Check if contribution is in any earning's formula
		chk = 0
		for e in doc.earnings:
			earn = frappe.get_doc("Salary Component", e.salary_component)
			for form in earn.deduction_contribution_formula:
				if c.salary_component == form.salary_component:
					chk = 1
		if chk == 1:
			c.amount = round((flt(c.default_amount) * flt(doc.payment_days_for_deductions)/tdim),0)
		tot_cont += c.amount
	
	doc.gross_pay = gross_pay
	doc.total_deduction = tot_ded
	doc.net_pay = doc.gross_pay - doc.total_deduction
	doc.rounded_total = myround(doc.net_pay, 10)
		
	company_currency = get_company_currency(doc.company)
	doc.total_in_words = money_in_words(doc.rounded_total, company_currency)
	doc.total_ctc = doc.gross_pay + tot_cont
	
def get_leaves(doc, start_date, end_date, emp):
	#Find out the number of leaves applied by the employee only working days
	lwp = 0 #Leaves without pay
	plw = 0 #paid leaves
	diff = (end_date - start_date).days + 1
	for day in range(0, diff):
		date = start_date + datetime.timedelta(days=day)
		auth_leaves = frappe.db.sql("""SELECT la.name FROM `tabLeave Application` la
			WHERE la.status = 'Approved' AND la.docstatus = 1 AND la.employee = '%s'
			AND la.from_date <= '%s' AND la.to_date >= '%s'""" % (doc.employee, date, date), as_list=1)
		if auth_leaves:
			auth_leaves = auth_leaves[0][0]
			lap = frappe.get_doc("Leave Application", auth_leaves)
			ltype = frappe.get_doc("Leave Type", lap.leave_type)
			hol = get_holidays(doc, date, date, emp)
			if hol:
				pass
			else:
				if ltype.is_lwp == 1:
					lwp += 1
				else:
					plw += 1
	lwp = flt(lwp)
	plw = flt(plw)
	return lwp,plw
	
def get_holidays(doc, start_date, end_date,emp):
	if emp.relieving_date is None:
		relieving_date = datetime.date(2099, 12, 31)
	else:
		relieving_date = emp.relieving_date
	
	if emp.date_of_joining > start_date:
		start_date = emp.date_of_joining
	
	if relieving_date < end_date:
		end_date = relieving_date
	
	holiday_list = get_holiday_list_for_employee(doc.employee)
	holidays = frappe.db.sql("""SELECT count(name) FROM `tabHoliday` WHERE parent = '%s' AND 
		holiday_date >= '%s' AND holiday_date <= '%s'""" %(holiday_list, \
			start_date, end_date), as_list=1)
	
	holidays = flt(holidays[0][0]) #no of holidays in a month from the holiday list
	return holidays

def get_total_days(doc, emp, msd, med, month):
	tdim = month["month_days"] #total days in a month
	if emp.relieving_date is None:
		relieving_date = datetime.date(2099, 12, 31)
	else:
		relieving_date = emp.relieving_date

	if emp.date_of_joining >= msd:
		twd = (med - emp.date_of_joining).days + 1 #Joining DATE IS THE First WORKING DAY
	elif relieving_date <= med:
		twd = (emp.relieving_date - msd).days + 1 #RELIEVING DATE IS THE LAST WORKING DAY
	else:
		twd = month["month_days"] #total days in a month
	return tdim, twd

def get_expense_claim(doc):
	m = get_month_details(doc.fiscal_year, doc.month)
	#Get total Expense Claims Due for an Employee
	query = """SELECT ec.name, ec.employee, ec.total_sanctioned_amount, ec.total_amount_reimbursed
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
				"idx": len(doc.earnings)+1, "depends_on_lwp": 0, "default_amount": (i[2]-i[3]), \
				"expense_claim": i[0], "salary_component": "Expense Claim", "amount": (i[2]- i[3])
			})

def get_loan_deduction(doc, msd, med):
	existing_loan = []
	for d in doc.deductions:
		existing_loan.append(d.employee_loan)
		
	#get total loan due for employee
	query = """SELECT el.name, eld.name, eld.emi, el.deduction_type, eld.loan_amount
		FROM 
			`tabEmployee Loan` el, `tabEmployee Loan Detail` eld
		WHERE
			eld.parent = el.name AND
			el.docstatus = 1 AND el.posting_date <= '%s' AND
			eld.employee = '%s'""" %(med, doc.employee)
		
	loan_list = frappe.db.sql(query, as_list=1)

	for i in loan_list:
		emi = i[2]
		total_loan = i[4]
		if i[0] not in existing_loan:
			#Check if the loan has already been deducted
			query = """SELECT SUM(ssd.amount) 
				FROM `tabSalary Detail` ssd, `tabSalary Slip` ss
				WHERE ss.docstatus = 1 AND
					ssd.parent = ss.name AND
					ssd.employee_loan = '%s' and ss.employee = '%s'""" %(i[0], doc.employee)
			deducted_amount = frappe.db.sql(query, as_list=1)

			if total_loan > deducted_amount[0][0]:
				#Add deduction for each loan separately
				#Check if EMI is less than balance
				balance = flt(total_loan) - flt(deducted_amount[0][0])
				if balance > emi:
					doc.append("deductions", {
						"idx": len(doc.deductions)+1, "depends_on_lwp": 0, "default_amount": emi, \
						"employee_loan": i[0], "salary_component": i[3], "amount": emi
					})
				else:
					doc.append("deductions", {
						"idx": len(doc.deductions)+1, "d_depends_on_lwp": 0, "default_amount": balance, \
						"employee_loan": i[0], "salary_component": i[3], "amount": balance
					})
	for d in doc.deductions:
		if d.employee_loan:
			total_given = frappe.db.sql("""SELECT eld.loan_amount 
				FROM `tabEmployee Loan` el, `tabEmployee Loan Detail` eld
				WHERE eld.parent = el.name AND eld.employee = '%s' 
				AND el.name = '%s'"""%(doc.employee, d.employee_loan), as_list=1)
			
			deducted = frappe.db.sql("""SELECT SUM(ssd.amount) 
				FROM `tabSalary Detail` ssd, `tabSalary Slip` ss
				WHERE ss.docstatus = 1 AND ssd.parent = ss.name 
				AND ssd.employee_loan = '%s' and ss.employee = '%s'"""%(d.employee_loan, doc.employee), as_list=1)
			balance = flt(total_given[0][0]) - flt(deducted[0][0])
			if balance < d.amount:
				frappe.throw(("Max deduction allowed {0} for Loan Deduction {1} \
				check row # {2} in Deduction Table").format(balance, d.employee_loan, d.idx))

def get_month_dates(doc):
	month = get_month_details(doc.fiscal_year, doc.month)
	msd = month.month_start_date
	med = month.month_end_date
	return month, msd, med


def get_edc(doc):
	#Earning Table should be replaced if there is any change in the Earning Composition
	#Change can be of 3 types in the earning table
	#1. If a user removes a type of earning
	#2. If a user adds a type of earning
	#3. If a user deletes and adds a type of another earning
	#Function to get the Earnings, Deductions and Contributions (E,D,C)

	sstr = frappe.get_doc("Salary Structure", doc.salary_structure)		
	existing_ded = []
	
	dict = {}
	for comp in doc.deductions:
		if comp.salary_component == 'Loan Deduction':
			dict['salary_component'] = comp.salary_component
			dict['idx'] = comp.idx
			dict['default_amount'] = comp.default_amount
			dict['amount'] = comp.amount
			dict['employee_loan'] = comp.employee_loan
			existing_ded.append(dict.copy())
			
	table_list = ["earnings", "deductions", "contributions"]
	doc.earnings = []
	doc.deductions = []
	doc.contributions = []
	get_from_sal_struct(doc, sstr, table_list)
	#Add changed loan amount to the table
	if existing_ded:
		doc.append("deductions", {
			"salary_component": dict['salary_component'],
			"default_amount": existing_ded[0]['default_amount'],
			"amount": existing_ded[0]['amount'],
			"idx": existing_ded[0]['idx'],
			"employee_loan": existing_ded[0]['employee_loan']
		})

def get_from_sal_struct(doc, salary_structure_doc, table_list):
	data = SalarySlip.get_data_for_eval(doc)

	for table_name in table_list:
		for comp in salary_structure_doc.get(table_name):
			amount = SalarySlip.eval_condition_and_formula(doc, comp, data)
			doc.append(table_name, {
				"salary_component": comp.salary_component,
				"default_amount": amount,
				"amount": amount,
				"idx": comp.idx,
				"depends_on_lwp": comp.depends_on_lwp
			})
			
def myround(x, base=5):
    return int(base * round(float(x)/base))
