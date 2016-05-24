# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import math
import datetime
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
	get_edc(doc, method)
	gross_pay = 0
	net_pay = 0
	tot_ded = 0
	tot_cont = 0

	m = get_month_details(doc.fiscal_year, doc.month)
	msd = m.month_start_date
	med = m.month_end_date
	emp = frappe.get_doc("Employee", doc.employee)
	
	tdim, twd = get_total_days(doc,method, emp, msd, med, m)
	
	get_loan_deduction(doc,method, msd, med)
	get_expense_claim(doc,method)
	holidays = get_holidays(doc, method, msd, med, emp)
	
	lwp, plw = get_leaves(doc, method, msd, med, emp)
	
	doc.leave_without_pay = lwp
		
	doc.posting_date = m.month_end_date
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
	
	doc.unauthorized_leaves = ual 
	
	ot_ded = round(8*ual,1)
	if ot_ded > t_ot:
		ot_ded = (int(t_ot/8))*8
	doc.overtime_deducted = ot_ded
	d_ual = int(ot_ded/8)
	#Calculate Earnings
	chk_ot = 0 #Check if there is an Overtime Rate
	for d in doc.earnings:
		if d.e_type == "Overtime Rate":
			chk_ot = 1
			
	for d in doc.earnings:
		earn = frappe.get_doc("Earning Type", d.e_type)
		if earn.depends_on_lwp == 1:
			d.e_depends_on_lwp = 1
		else:
			d.e_depends_on_lwp = 0
			
		if earn.based_on_overtime:
			for d2 in doc.earnings:
				#Calculate Overtime Value
				if earn.overtime_rate == d2.e_type:
					d.e_amount = flt(d2.e_amount) * t_ot
					d.e_modified_amount = flt(d2.e_amount) * (t_ot - ot_ded)
		else:
			if d.e_depends_on_lwp == 1:
				if chk_ot == 1:
					d.e_modified_amount = round(flt(d.e_amount) * (paydays+d_ual)/tdim,0)
				else:
					d.e_modified_amount = round(flt(d.e_amount) * (paydays)/tdim,0)
			else:
				d.e_modified_amount = d.e_amount
		
		if earn.only_for_deductions <> 1:
			gross_pay += flt(d.e_modified_amount)
		else:
			if d.e_type <> "Overtime Rate":
				d.e_modified_amount = round(flt(d.e_amount) * pd_ded/tdim,0)

	if gross_pay < 0:
		doc.arrear_amount = -1 * gross_pay
	gross_pay += flt(doc.arrear_amount) + flt(doc.leave_encashment_amount)
	
	#Calculate Deductions
	for d in doc.deductions:
		deduct = frappe.get_doc("Deduction Type", d.d_type)
		if deduct.based_on_earning:
			d.d_modified_amount = 0
			for e in doc.earnings:
				en = frappe.get_doc("Earning Type", e.e_type)
				if en.only_for_deductions == 1:
					for link in en.deduction_table:
						if link.deduction_type == d.d_type:
							d.d_modified_amount += round((flt(e.e_modified_amount) * link.percentage/100),0)
		else:
			if deduct.based_on_lwp == 1:
					d.d_modified_amount = round((flt(d.d_amount) * flt(doc.payment_days_for_deductions)/tdim),0)
			else:
				if d.d_type <> "Loan Deduction":
					d.d_modified_amount = d.d_amount
		tot_ded +=d.d_modified_amount
	
	#Calculate Contributions
	for c in doc.contributions:
		cont = frappe.get_doc("Contribution Type", c.contribution_type)
		if cont.based_on_earning:
			c.modified_amount = 0
			for e in doc.earnings:
				en = frappe.get_doc("Earning Type", e.e_type)
				if en.only_for_deductions == 1:
					for link in en.contribution_table:
						if link.contribution_type == c.contribution_type:
							c.modified_amount += round((flt(e.e_modified_amount) * link.percentage/100),0)
		tot_cont += c.modified_amount
	
	doc.gross_pay = gross_pay
	doc.total_deduction = tot_ded
	doc.payment_days = paydays
	if doc.change_deductions == 0:
		doc.payment_days_for_deductions = doc.payment_days
	doc.net_pay = doc.gross_pay - doc.total_deduction
	doc.rounded_total = myround(doc.net_pay, 10)
		
	company_currency = get_company_currency(doc.company)
	doc.total_in_words = money_in_words(doc.rounded_total, company_currency)
	doc.total_ctc = doc.gross_pay + tot_cont

def get_total_days(doc,method, emp, msd, med, month):
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
	
def get_leaves(doc, method, start_date, end_date, emp):
	#Find out the number of leaves applied by the employee only working days
	lwp = 0 #Leaves without pay
	plw = 0 #paid leaves
	diff = (end_date - start_date).days
	
	for day in range(0, diff):
		date = start_date + datetime.timedelta(days=day)
		auth_leaves = frappe.db.sql("""SELECT la.name FROM `tabLeave Application` la
			WHERE la.status = 'Approved' AND la.docstatus = 1 AND la.employee = '%s'
			AND la.from_date <= '%s' AND la.to_date >= '%s'""" % (doc.employee, date, date), as_list=1)
		if auth_leaves:
			auth_leaves = auth_leaves[0][0]
			lap = frappe.get_doc("Leave Application", auth_leaves)
			ltype = frappe.get_doc("Leave Type", lap.leave_type)
			hol = get_holidays(doc,method, date, date, emp)
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
		
def get_holidays(doc,method, start_date, end_date,emp):
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
	
def get_loan_deduction(doc,method, msd, med):
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
			query = """SELECT SUM(ssd.d_modified_amount) 
				FROM `tabSalary Slip Deduction` ssd, `tabSalary Slip` ss
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
						"idx": len(doc.deductions)+1, "d_depends_on_lwp": 0, "d_modified_amount": emi, \
						"employee_loan": i[0], "d_type": i[3], "d_amount": emi
					})
				else:
					doc.append("deductions", {
						"idx": len(doc.deductions)+1, "d_depends_on_lwp": 0, "d_modified_amount": balance, \
						"employee_loan": i[0], "d_type": i[3], "d_amount": balance
					})
	for d in doc.deductions:
		if d.employee_loan:
			total_given = frappe.db.sql("""SELECT eld.loan_amount 
				FROM `tabEmployee Loan` el, `tabEmployee Loan Detail` eld
				WHERE eld.parent = el.name AND eld.employee = '%s' 
				AND el.name = '%s'"""%(doc.employee, d.employee_loan), as_list=1)
			
			deducted = frappe.db.sql("""SELECT SUM(ssd.d_modified_amount) 
				FROM `tabSalary Slip Deduction` ssd, `tabSalary Slip` ss
				WHERE ss.docstatus = 1 AND ssd.parent = ss.name 
				AND ssd.employee_loan = '%s' and ss.employee = '%s'"""%(d.employee_loan, doc.employee), as_list=1)
			balance = flt(total_given[0][0]) - flt(deducted[0][0])
			if balance < d.d_modified_amount:
				frappe.throw(("Max deduction allowed {0} for Loan Deduction {1} \
				check row # {2} in Deduction Table").format(balance, d.employee_loan, d.idx))

def get_expense_claim(doc,method):
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
				"idx": len(doc.earnings)+1, "e_depends_on_lwp": 0, "e_modified_amount": (i[2]-i[3]), \
				"expense_claim": i[0], "e_type": "Expense Claim", "e_amount": (i[2]- i[3])
			})

def get_edc(doc,method):
	#Earning Table should be replaced if there is any change in the Earning Composition
	#Change can be of 3 types in the earning table
	#1. If a user removes a type of earning
	#2. If a user adds a type of earning
	#3. If a user deletes and adds a type of another earning
	#Function to get the Earnings, Deductions and Contributions (E,D,C)

	m = get_month_details(doc.fiscal_year, doc.month)
	emp = frappe.get_doc("Employee", doc.employee)
	joining_date = emp.date_of_joining
	if emp.relieving_date:
		relieving_date = emp.relieving_date
	else:
		relieving_date = '2099-12-31'
	
	struct = frappe.db.sql("""SELECT name FROM `tabSalary Structure` WHERE employee = %s AND
		is_active = 'Yes' AND (from_date <= %s OR from_date <= %s) AND
		(to_date IS NULL OR to_date >= %s OR to_date >= %s)""", 
		(doc.employee, m.month_start_date, joining_date, m.month_end_date, relieving_date))
	if struct:
		sstr = frappe.get_doc("Salary Structure", struct[0][0])
	else:
		frappe.throw("No active Salary Structure for this period")
		
	contri_amount = 0
	doc.contributions = []
	existing_ded = []
	

			
	for d in doc.deductions:
		existing_ded.append(d.d_type)
	
	earn = 0
	#Update Earning Table if the Earning table is empty
	if doc.earnings:
		pass
	else:
		earn = 1
		
	for e in doc.earnings:
		found = 0
		for ess in sstr.earnings:
			if e.e_type == ess.e_type and e.idx == ess.idx and found== 0:
				found = 1
		if found == 0 and earn == 0:
			if e.e_type <> "Expense Claim":
				earn = 1
	
	if earn == 1:
		doc.earnings = []
		for e in sstr.earnings:
			doc.append("earnings",{
				"e_type": e.e_type,
				"e_amount": e.modified_value,
				"e_modified_amount": e.modified_value,
				"idx": e.idx
			})
			
	ded = 0
	if doc.deductions:
		pass
	else:
		ded = 1

	for d in doc.deductions:
		found = 0
		for dss in sstr.deductions:
			if d.d_type == dss.d_type and d.idx == dss.idx and found == 0:
				found = 1
		if found == 0 and ded == 0:
			if d.d_type <> "Loan Deduction":
				ded = 1
				
	if ded == 1:
		doc.deductions = []
		for d in sstr.deductions:
			doc.append("deductions",{
				"d_type": d.d_type,
				"d_amount": d.d_modified_amt,
				"d_modified_amount": d.d_modified_amt,
				"d.idx": d.idx
			})
	
	for c in sstr.contributions:
		contri = frappe.get_doc("Contribution Type", c.contribution_type)
		if contri.based_on_earning == 1:
			for e in doc.earnings:
				if contri.earning == e.e_type:
					contri_amount = round(contri.percentage * e.e_modified_amount/100,0)
			
		doc.append("contributions",{
			"contribution_type": c.contribution_type,
			"default_amount": c.amount,
			"modified_amount": contri_amount
			})
		
def myround(x, base=5):
    return int(base * round(float(x)/base))

	