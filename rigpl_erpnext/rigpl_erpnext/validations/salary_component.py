# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
	if doc.is_earning == 1:
		if doc.is_deduction == 1 or doc.is_contribution == 1:
			frappe.throw("Salary Component can either be Earning or Deduction or Contribution")
	
	if doc.is_deduction == 1:
		if doc.is_earning == 1 or doc.is_contribution == 1:
			frappe.throw("Salary Component can either be Earning or Deduction or Contribution")
			
	if doc.is_contribution == 1:
		if doc.is_earning == 1 or doc.is_deduction == 1:
			frappe.throw("Salary Component can either be Earning or Deduction or Contribution")
			
	if doc.is_contribution == 0 and doc.is_deduction == 0 and doc.is_earning == 0:
		frappe.throw("Salary Component has to be either of Earning or Deduction or Contribution")