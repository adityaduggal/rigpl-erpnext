# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import sys
from frappe.utils import flt
from rigpl_erpnext.utils.item_utils import *

#Run this script every hour but to ensure that there is no server overload run it only for 1 template at a time

def check_wrong_variants():
	copy_from_template()

def copy_from_template():
	limit_set = int(frappe.db.get_single_value("Stock Settings", "automatic_sync_field_limit"))
	is_sync_allowed = frappe.db.get_single_value("Stock Settings", 
		"automatically_sync_templates_data_to_items")
	if is_sync_allowed == 1:
		templates = frappe.db.sql("""SELECT it.name, (SELECT count(name) 
			FROM `tabItem` WHERE variant_of = it.name) as variants 
			FROM `tabItem` it WHERE it.has_variants = 1 
			AND it.disabled = 0 AND it.end_of_life >= CURDATE()
			ORDER BY variants DESC""", as_list=1)
		sno = 0
		for t in templates:
			sno += 1
			print (str(sno) + " " + t[0] + " has variants = " + str(t[1]))
		fields_edited = 0
		it_lst = []
		for t in templates:
			print (str(t[0]) + " Has No of Variants = " + str(t[1]))
			if fields_edited <= limit_set:
				temp_doc = frappe.get_doc("Item", t[0])
				variants = frappe.db.sql("""SELECT name FROM `tabItem` WHERE variant_of = '%s'
					ORDER BY name ASC"""%(t[0]), as_list=1)
				#Check all variants' fields are matching with template if 
				#not then copy the fields else go to next item
				for item in variants:
					check = 0
					print ("Checking Item = " + item[0])
					it_doc = frappe.get_doc("Item", item[0])
					validate_variants(it_doc)
					check += check_and_copy_attributes_to_variant(temp_doc, it_doc)
					fields_edited += check
					#if check > 0:
					#	it_lst.append(item[0])
			else:
				print ("Limit of " + str(limit_set) + " fields reached. Run again for more updating")
				break
			frappe.db.commit()