# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def execute():
	table_list = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"]
	for t in table_list:
		table_name = '`tab' + t + ' Item`'
		dt_name = t + ' Item'
		qod_no_pl = frappe.db.sql("""SELECT name, parent ,item_code FROM %s 
			WHERE price_list IS NULL
			ORDER BY creation""" % (table_name), as_list=1)
		if qod_no_pl:
			for qod in qod_no_pl:
				qod_doc = frappe.get_doc(dt_name, qod[0])
				dt_pl = frappe.get_value(t, qod[1], "selling_price_list")
				if dt_pl:
					frappe.db.set_value(dt_name, qod[0], "price_list", dt_pl)
					print("Updated Price List for " + t + "# " \
						+ qod_doc.parent + " Item No: " + str(qod_doc.idx))
				else:
					print( t + " # " + qod_doc.parent + " Does Not have Price List")
		frappe.db.commit()
		print("Committed Changes")