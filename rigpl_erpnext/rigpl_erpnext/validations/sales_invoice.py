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
	for d in doc.entries:
		#frappe.msgprint(("Row#{0}: Item Code = {1} and SO# = {2}").format(d.idx, d.item_code, d.sales_order))
		if d.sales_order is not None:
			if d.delivery_note is None:
				frappe.msgprint(("""Error in Row# {0} has SO# {1} but there is no DN.
				Hence making of Invoice is DENIED""").format(d.idx, d.sales_order), raise_exception=1)
		elif d.delivery_note is not None:
			if d.sales_order is None:
				frappe.msgprint(("""Error in Row# {0} has DN# {1} but there is no SO.
				Hence making of Invoice is DENIED""").format(d.idx, d.delivery_note), raise_exception=1)
