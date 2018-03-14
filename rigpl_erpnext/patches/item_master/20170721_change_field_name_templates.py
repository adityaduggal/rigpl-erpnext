# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute():
	print ("Welcome to the Script to Change the Field Names of Templates Programmatically")
	attribute_name = raw_input("Enter the Attribute Name you want to Change exactly as in ERP: ")
	new_field_name = raw_input("Enter the Field Name for Website for above attribute: ")
	#item_name_like = raw_input("Enter the Items Like (Hit Enter if NO Value): ")
	
	change_list = frappe.db.sql("""SELECT iva.name, iva.parent, iva.attribute, iva.prefix, iva.field_name, iva.suffix 
		FROM `tabItem Variant Attribute` iva, `tabItem` it 
		WHERE iva.parent = it.name AND it.has_variants = 1 AND iva.attribute = '%s'
		ORDER BY iva.parent, iva.idx""" %(attribute_name), as_list = 1)

	for i in change_list:
		frappe.db.sql("""UPDATE `tabItem Variant Attribute` 
			SET field_name = '%s' 
			WHERE name = '%s' AND field_name != 'Material'"""%(new_field_name, i[0]))