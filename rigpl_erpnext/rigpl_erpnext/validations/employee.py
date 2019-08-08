# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe, re
from frappe import _
from rigpl_erpnext.utils.rigpl_perm import *
from frappe import msgprint
from frappe.utils import getdate
from datetime import datetime
from dateutil.relativedelta import relativedelta
from rigpl_erpnext.utils.other_utils import validate_pan, validate_aadhaar
import time

def validate(doc,method):
	#Validation for Age of Employee should be Greater than 18 years at the time of Joining.
	dob = getdate(doc.date_of_birth)
	doj = getdate(doc.date_of_joining)
	if relativedelta(doj, dob).years < 18:
		frappe.msgprint("Not Allowed to Create Employees under 18 years of Age", raise_exception = 1)
	if doc.relieving_date:
		if doc.status != "Left":
			frappe.msgprint("Status has to be 'LEFT' as the Relieving Date is populated",raise_exception =1)
	if doc.status == "Left":
		doc.department = "All Departments"

	if doc.department == "":
		frappe.throw("Department is Manadatory for Employee {}".format(doc.name))
			
	doc.employee_number = doc.name
	doc.employee = doc.name
	if doc.aadhaar_number:
		validate_aadhaar(doc.aadhaar_number)
	if doc.pan_number:
		validate_pan(doc.pan_number)

def on_update(doc,method):
	allowed_ids = []
	allowed_ids = get_employees_allowed_ids(doc.employee)
	for user in allowed_ids:
		role_list = get_user_roles(user)
		role_in_settings, apply_to_all_doctypes, applicable_for = \
			check_role(role_list, "Employee", apply_to_all_doctypes="None")
		if role_in_settings == 1:
			create_new_user_perm(allow="Employee", for_value=doc.name, \
				user=user, apply_to_all_doctypes=apply_to_all_doctypes, \
				applicable_for=applicable_for)
	emp_perm_list = get_permission(allow="Employee", for_value=doc.name)
	for perm in emp_perm_list:
		if perm[3] not in allowed_ids:
			delete_permission(perm[0])
	
def autoname(doc,method):
	doj = getdate(doc.date_of_joining)
	id = frappe.db.sql("""SELECT current FROM `tabSeries` WHERE name = '%s'""" %doc.naming_series, as_list=1)
	id = str(id[0][0])
	#Generate employee number on the following logic
	#Employee Number would be YYYYMMDDXXXXC, where:
	#YYYYMMDD = Date of Joining in YYYYMMDD format
	#XXXX = Serial Number of the employee from the ID this is NUMBERIC only
	#C= Check DIGIT
	if doc.date_of_joining:
		doj = str(doj.year) + str(doj.month).zfill(2)
		code = doj+id
		check = fn_check_digit(doc, code)
		code = code + str(check)
	doc.name = code

	
###############~Code to generate the CHECK DIGIT~###############################
#Link: https://wiki.openmrs.org/display/docs/Check+Digit+Algorithm
################################################################################
def fn_check_digit(doc,id_without_check):

	# allowable characters within identifier
	valid_chars = "0123456789ABCDEFGHJKLMNPQRSTUVYWXZ"

	# remove leading or trailing whitespace, convert to uppercase
	id_without_checkdigit = id_without_check.strip().upper()

	# this will be a running total
	sum = 0;

	# loop through digits from right to left
	for n, char in enumerate(reversed(id_without_checkdigit)):

			if not valid_chars.count(char):
					raise Exception('InvalidIDException')

			# our "digit" is calculated using ASCII value - 48
			digit = ord(char) - 48

			# weight will be the current digit's contribution to
			# the running total
			weight = None
			if (n % 2 == 0):

					# for alternating digits starting with the rightmost, we
					# use our formula this is the same as multiplying x 2 &
					# adding digits together for values 0 to 9.  Using the
					# following formula allows us to gracefully calculate a
					# weight for non-numeric "digits" as well (from their
					# ASCII value - 48).
					weight = (2 * digit) - int((digit / 5)) * 9
			else:
					# even-positioned digits just contribute their ascii
					# value minus 48
					weight = digit

			# keep a running total of weights
			sum += weight

	# avoid sum less than 10 (if characters below "0" allowed,
	# this could happen)
	sum = abs(sum) + 10

	# check digit is amount needed to reach next number
	# divisible by ten. Return an integer
	return int((10 - (sum % 10)) % 10)
