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