# -*- coding: utf-8 -*-
import frappe

def execute():
	#Copy the Salary Structure Contribution Table to Salary Detail
	frappe.db.sql("""INSERT INTO `tabSalary Detail` (`name`, `creation`, `modified`, `modified_by`, 
		`owner`, `docstatus`, `parent`, `parentfield`, `parenttype`, `idx`, `amount`, 
		`salary_component`) SELECT `name`, `creation`, `modified`, `modified_by`, 
		`owner`, `docstatus`, `parent`, `parentfield`, `parenttype`, `idx`, `amount`, 
		`contribution_type` FROM `tabSalary Structure Contribution` WHERE `name` NOT IN
		(SELECT `name` FROM `tabSalary Detail`)""")
	
	#Copy the Salary Slip Contribution Table to Salary Detail
	frappe.db.sql("""INSERT INTO `tabSalary Detail` (`name`, `creation`, `modified`, `modified_by`, 
		`owner`, `docstatus`, `parent`, `parentfield`, `parenttype`, `idx`, `default_amount`,
		`amount`, `salary_component`) SELECT `name`, `creation`, `modified`, `modified_by`, 
		`owner`, `docstatus`, `parent`, `parentfield`, `parenttype`, `idx`, `default_amount`, 
		`modified_amount`, `contribution_type` FROM `tabSalary Slip Contribution`
		WHERE `name` NOT IN (SELECT `name` FROM `tabSalary Detail`)""")
	
	#Correct the default_amount is NOT there in Salary Detail incase of Salary Structure
	frappe.db.sql("""UPDATE `tabSalary Detail` SET amount = default_amount, default_amount = 0
		WHERE parenttype = 'Salary Structure' AND default_amount >0 AND amount = 0""")
	
	#Get the Expense Claim into the Salary Detail Table
	frappe.db.sql("""UPDATE `tabSalary Detail` sd INNER JOIN `tabSalary Slip Earning` sse
		ON (sd.name = sse.name AND sd.parenttype = 'Salary Slip')
		SET sd.expense_claim = sse.expense_claim""")
	
	#Get the Employee Loan into the Salary Detail Table
	frappe.db.sql("""UPDATE `tabSalary Detail` sd INNER JOIN `tabSalary Slip Deduction` ssd
		ON (sd.name = ssd.name AND sd.parenttype = 'Salary Slip')
		SET sd.employee_loan = ssd.employee_loan""")