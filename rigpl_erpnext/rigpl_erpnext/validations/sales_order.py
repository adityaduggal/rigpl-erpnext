# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	letter_head= frappe.db.get_value("Sales Taxes and Charges Master", doc.taxes_and_charges ,"letter_head")
	if (doc.letter_head != letter_head):
		frappe.msgprint("Letter Head selected does not match with Sales Tax", raise_exception=1)
