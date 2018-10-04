# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute():
	print ("Welcome to the Script to Change the Attribute Value of Item Code Programmatically")
	item_code = raw_input("Enter the Item Code you want to Change exactly as in ERP: ")
	attr_name = raw_input("Enter the Field Name for Item to be Changed: ")
	attr_value = raw_input("Enter the New Value: ")

	change_list = frappe.db.sql("""SELECT iva.name, iva.parent, iva.attribute, iva.attribute_value 
		FROM `tabItem Variant Attribute` iva
		WHERE iva.parent = '%s' AND iva.attribute = '%s'
		ORDER BY iva.parent, iva.idx""" %(item_code, attr_name), as_list = 1)
	
	if change_list:
		for i in change_list:
			frappe.db.sql("""UPDATE `tabItem Variant Attribute` 
				SET attribute_value = '%s' 
				WHERE name = '%s' """%(attr_value, i[0]))