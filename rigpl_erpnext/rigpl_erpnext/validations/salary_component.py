# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
	"""
	Validate Salary Component for HRMS v16 compatibility.
	
	HRMS v16 uses:
	- type field: 'Earning' or 'Deduction'
	- accrual_component: for employer contributions (formerly is_contribution)
	
	Legacy RIGPL fields (kept for backward compatibility):
	- is_earning, is_deduction, is_contribution
	"""
	
	# HRMS v16 validation: type field is required
	if not doc.type:
		# Try to infer from legacy fields for backward compatibility
		if doc.get("is_earning") == 1 or doc.get("is_contribution") == 1:
			doc.type = "Earning"
		elif doc.get("is_deduction") == 1:
			doc.type = "Deduction"
		else:
			frappe.throw("Salary Component must have a Type (Earning or Deduction)")
	
	# Validate accrual_component is only for Earning type
	if doc.get("accrual_component") == 1 and doc.type != "Earning":
		frappe.throw("Accrual Component can only be set for Earning type Salary Components")
	
	# Sync legacy is_contribution with accrual_component for backward compatibility
	if doc.get("is_contribution") == 1 and doc.get("accrual_component") != 1:
		doc.accrual_component = 1
	
	# Sync legacy fields with type (for reports that may still use them)
	if doc.type == "Earning":
		if doc.get("accrual_component") == 1:
			doc.is_contribution = 1
			doc.is_earning = 0
		else:
			doc.is_earning = 1
			doc.is_contribution = 0
		doc.is_deduction = 0
	elif doc.type == "Deduction":
		doc.is_deduction = 1
		doc.is_earning = 0
		doc.is_contribution = 0
