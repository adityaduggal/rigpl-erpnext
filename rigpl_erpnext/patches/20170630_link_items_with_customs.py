# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe, erpnext
from frappe.utils import flt
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_month_details

def execute():
	'''
	This patch would add the Customs Code and Country of Origin in all Items (Non-Template)
	'''
	items = frappe.db.sql("""SELECT it.name, iva.attribute_value
		FROM `tabItem` it , `tabItem Variant Attribute` iva
		WHERE it.has_variants = 0 AND it.customs_tariff_number IS NULL
			AND iva.parent = it.name
			AND iva.attribute = 'CETSH Number' 
			AND it.disabled = 0
			AND IFNULL(it.end_of_life, '2099-12-31')> CURDATE()
		ORDER BY it.name""", as_list=1)
	count = 0
	for item in items:
		item_doc = frappe.get_doc("Item", item[0])
		count += 1
		custom_tariffs = frappe.db.sql("""SELECT name 
			FROM `tabCustoms Tariff Number`""", as_list =1)
		dont_create = 0
		for tariff in custom_tariffs:
			if item[1] not in tariff:
				dont_create += 0
			else:
				dont_create += 1
		
		if dont_create == 0:
			new_tariff = frappe.new_doc("Customs Tariff Number")
			new_tariff.name = item[1]
			new_tariff.tariff_number = item[1]
			new_tariff.description = "New"
			new_tariff.insert()
			print ("S.No. " + str(count) + " Tariff= " + item[1] + " created")
		frappe.db.set_value("Item", item[0], "country_of_origin", 'India')
		frappe.db.set_value("Item", item[0], "customs_tariff_number", item[1])
		print ("S.No. " + str(count) + " Item Code= " + item[0] + " updated with Customs number = " + item[1])
