# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from rigpl_erpnext.utils.other_utils import validate_msme_no, validate_pan

def validate(doc,method):
	msme_validations(doc, method)

def msme_validations(doc, method):
	if doc.is_msme_registered == 1:
		if not doc.msme_number:
			frappe.throw("MSME Number is Mandatory for {}".format(doc.name))
	if doc.msme_number:
		validate_msme_no(doc.msme_number)
		if not doc.pan:
			frappe.throw("Pan No is Mandatory for MSME Supplier {}".format(doc.name))
		else:
			validate_pan(doc.pan)