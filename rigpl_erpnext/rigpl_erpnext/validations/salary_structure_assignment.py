# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_start_end_dates

def validate(doc,method):
	#Validate From Date should be first date of month
	if doc.from_date > doc.to_date:
		frappe.throw("From Date cannot be after To Date")

	date_details = get_start_end_dates("Monthly", doc.from_date)
	doj = frappe.db.get_value("Employee", doc.employee, "date_of_joining")

	if doj < date_details.end_date and doj >= date_details.start_date:
		doc.from_date = doj
	else:
		doc.from_date = date_details.start_date

	if doc.minimum_applicable > 0:
		if doc.basic_percent > 0:
			if ((doc.base + doc.variable) * doc.basic_percent)/100 < doc.minimum_applicable:
				frappe.throw("Basic Salary Cannot be Less than Minimum Applicable")