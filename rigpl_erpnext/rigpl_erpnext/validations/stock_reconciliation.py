# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	#Get Stock Valuation from Item Table
	for d in doc.items:
		query = """SELECT valuation_rate FROM `tabItem` WHERE name = '%s' """ % d.item_code
		vr = frappe.db.sql(query, as_list=1)
		if vr[0][0] != 0 or vr[0][0]:
			if d.warehouse == "REJ-DEL20A - RIGPL":
				d.valuation_rate = 1
			else:
				d.valuation_rate = vr[0][0]
		else:
			d.valuation_rate = 1	