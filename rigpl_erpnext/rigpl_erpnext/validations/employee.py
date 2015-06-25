# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

def validate(doc,method):
	#Validation for Age of Employee should be Greater than 18 years at the time of Joining.
	dob = datetime.strptime(doc.date_of_birth, "%Y-%m-%d")
	doj = datetime.strptime(doc.date_of_joining, "%Y-%m-%d")
	if relativedelta(doj, dob).years < 18:
		frappe.msgprint("Not Allowed to Create Employees under 18 years of Age", raise_exception = 1)
	if doc.relieving_date:
		if doc.relieving_date < time.strftime("%Y-%m-%d"):
			if doc.status <> "Left":
				frappe.msgprint("Status has to be 'LEFT' as the Relieving Date is populated",raise_exception =1)