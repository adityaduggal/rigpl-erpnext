# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	#Get Stock Valuation from Valuation Rate Table
	for d in doc.items:
		query = """SELECT vr.name FROM `tabValuation Rate` vr where vr.disabled = 'No' and vr.item_code = '%s' """ % d.item_code
		vr_name = frappe.db.sql(query, as_list=1)
		if vr_name <> []:
			vr = frappe.get_doc("Valuation Rate", vr_name[0][0])
			if d.item_code == vr.item_code:
				d.basic_rate = vr.valuation_rate
				d.valuation_rate = vr.valuation_rate