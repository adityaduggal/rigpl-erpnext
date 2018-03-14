# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import money_in_words, flt

def validate(doc,method):
	list = ['earnings', 'deductions', 'contributions']
	check_edc(doc, list)
	
def check_edc(doc,tables):
	#Only allow Earnings in Earnings Table and So On
	for i in tables:
		for comp in doc.get(i):
			sal_comp = frappe.get_doc("Salary Component", comp.salary_component)
			field = 'is_' + i[:-1]
			comp.depends_on_lwp = sal_comp.depends_on_lwp
			if sal_comp.get(field)!=1:
				frappe.throw(("Only {0} are allowed in {1} table check row# \
					{2} where {3} is not a {4}").format(i, i, comp.idx, \
					sal_comp.salary_component, i[:-1]))
	#Check for existing Salary Structures for Employees in Same Period
	for emp in doc.employees:
		if emp.to_date:
			to_date = emp.to_date
		else:
			to_date = '2099-12-31'
			
		query = """SELECT ss.name FROM `tabSalary Structure` ss,
			`tabSalary Structure Employee` sse WHERE sse.parent = ss.name AND
			ss.docstatus = 0 AND ss.name != '%s' AND 
			sse.employee = %s AND ((sse.from_date BETWEEN '%s' AND '%s') OR
			(IFNULL(sse.to_date, '2099-12-31') BETWEEN '%s' AND '%s'))""" \
			%(doc.name, emp.employee,emp.from_date, to_date, emp.from_date, to_date)

		existing_ss = frappe.db.sql(query, as_list=1)
		if existing_ss:
			frappe.throw(("For Row# {0} and Employee: {1} there is an existing \
			Salary Structure: {2} which is overlapping with the period of the current\
			Salary Structure. Kindly either disable Salary Structure: {3} or change the\
			From or To Date.").format(emp.idx, emp.employee_name, existing_ss[0][0],\
			existing_ss[0][0]))
