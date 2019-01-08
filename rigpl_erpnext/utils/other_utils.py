# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, re

def validate_ifsc_code(ifsc_code):
	if len(ifsc_code) != 11:
		frappe.throw('Invalid IFSC Length')
	p = re.compile("[0-9A-Z]{4}[0]{1}[0-9A-Z]{6}")
	if not p.match(ifsc_code):
		frappe.throw("Invalid IFSC Code")

def validate_brc_no(brc, ifsc):
	if len(brc) != 20:
		frappe.throw('Invalid BRC Length')
	if brc[:11] != ifsc:
		frappe.msgprint(brc[:11])
		frappe.throw("Invalid BRC Number")
	p = re.compile("[0-9A-Z]{11}[0-9]{9}")
	if not p.match(brc):
		frappe.throw("Invalid BRC Number")