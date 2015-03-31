# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	c_form_tax =frappe.db.get_value("Sales Taxes and Charges Master", doc.taxes_and_charges ,"c_form_applicable")
	letter_head= frappe.db.get_value("Sales Taxes and Charges Master", doc.taxes_and_charges ,"letter_head")
	if (doc.c_form_applicable != c_form_tax):
		frappe.msgprint("C-Form applicable selection does not match with Sales Tax", raise_exception=1)
	if (doc.letter_head != letter_head):
		frappe.msgprint("Letter Head selected does not match with Sales Tax", raise_exception=1)
