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

def validate_msme_no(msme_no):
	if len(msme_no)!= 12:
		frappe.throw("Invalid MSME No {}, it should be 12 Digits".format(msme_no))

	p = re.compile("[A-Z]{2}[0-9]{2}[A-Z]{1}[0-9]{7}")
	if not p.match(msme_no):
		frappe.throw("MSME No {} does not follow the format AB01C2345678".format(msme_no))

def validate_pan(pan):
	if pan:
		p = re.compile("[A-Z]{5}[0-9]{4}[A-Z]{1}")
		if not p.match(pan):
			frappe.throw(_("Invalid PAN Number {}".format(pan)))

def validate_aadhaar(aadhaar):
	if aadhaar:
		p = re.compile("[0-9]{12}")
	if not p.match(aadhaar):
		frappe.throw(_("Invalid Aadhaar Number"))
	aadhaar_check_digit = calcsum(aadhaar[:-1])
	if aadhaar[-1:] != str(aadhaar_check_digit):
		frappe.throw(_("Invalid Aadhaar Number"))

verhoeff_table_d = (
    (0,1,2,3,4,5,6,7,8,9),
    (1,2,3,4,0,6,7,8,9,5),
    (2,3,4,0,1,7,8,9,5,6),
    (3,4,0,1,2,8,9,5,6,7),
    (4,0,1,2,3,9,5,6,7,8),
    (5,9,8,7,6,0,4,3,2,1),
    (6,5,9,8,7,1,0,4,3,2),
    (7,6,5,9,8,2,1,0,4,3),
    (8,7,6,5,9,3,2,1,0,4),
    (9,8,7,6,5,4,3,2,1,0))

verhoeff_table_p = (
    (0,1,2,3,4,5,6,7,8,9),
    (1,5,7,6,2,8,3,0,9,4),
    (5,8,0,3,7,9,6,1,4,2),
    (8,9,1,6,0,4,3,5,2,7),
    (9,4,5,3,1,2,6,8,7,0),
    (4,2,8,6,5,7,3,9,0,1),
    (2,7,9,3,8,0,6,4,1,5),
    (7,0,4,6,9,1,3,2,5,8))

verhoeff_table_inv = (0,4,3,2,1,5,6,7,8,9)

def calcsum(number):
    """For a given number returns a Verhoeff checksum digit"""
    c = 0
    for i, item in enumerate(reversed(str(number))):
        c = verhoeff_table_d[c][verhoeff_table_p[(i+1)%8][int(item)]]
    return verhoeff_table_inv[c]