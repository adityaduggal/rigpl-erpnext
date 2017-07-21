# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute ():
	templates = frappe.db.sql("""SELECT it.name, ivr.allowed_values FROM `tabItem` it, `tabItem Variant Restrictions` ivr 
		WHERE it.has_variants = 1 AND ivr.parent = it.name AND ivr.attribute = 'CETSH Number'""", as_list =1)
	for t in templates:
		frappe.db.set_value("Item", t[0], "country_of_origin", 'India')
		frappe.db.set_value("Item", t[0], 'customs_tariff_number', t[1])
		print ("Updated Item " + t[0] + "Customs Tariff = " + t[1])