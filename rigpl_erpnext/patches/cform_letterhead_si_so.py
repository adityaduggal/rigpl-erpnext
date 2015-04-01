# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def execute():
	frappe.db.sql("""UPDATE `tabSales Invoice` si, `tabSales Taxes and Charges Master` sm
		SET si.c_form_applicable = sm.c_form_applicable,
		si.letter_head = sm.letter_head
		WHERE si.taxes_and_charges = sm.name """)
	
	frappe.db.sql("""UPDATE `tabSales Order` so, `tabSales Taxes and Charges Master` sm
		SET so.letter_head = sm.letter_head
		WHERE so.taxes_and_charges = sm.name """)
