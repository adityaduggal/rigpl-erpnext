# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def execute():
	frappe.db.sql("""UPDATE `tabDelivery Note Item` dni, `tabSales Taxes and Charges Master` sm,
		`tabDelivery Note` dn
		SET dni.rate = (FLOOR(dni.rate * 1.125*100))/100,
		dni.amount = (dni.rate * dni.qty)
		WHERE dn.docstatus = 1 AND dn.name = dni.parent AND
		dn.taxes_and_charges = 'RIGB CST2+ED' OR
		dn.taxes_and_charges = 'RIGB CST5+ED' OR
		dn.taxes_and_charges = 'RIGB VAT5+ED' OR
		dn.taxes_and_charges = 'RIGB VAT4+ED D1 Form' AND
		(dni.qty - ifnull((select sum(sid.qty) FROM `tabSales Invoice Item` sid, `tabSales Invoice` si
        	WHERE sid.delivery_note = dn.name and
			sid.parent = si.name and
        	sid.dn_detail = dni.name %s), 0)>=1)""")